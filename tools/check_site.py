#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTBU-STA 官网 · 一致性检查
==========================
本站的内容层是「数据 + 模板 + 构建」三层：content/site.json 存数据，
tools/template.html 存结构，index.html 由 tools/build.py 构建产出。
本脚本守住这条链路，避免出现「改了数据但页面没变」「合计数忘了联动」
「图片路径写错」这类问题。

检查项
------
A  数据结构    —— 必填字段是否齐全、类型是否正确
B  明细自洽    —— 每项赛事的报名/获奖数是否合理
C  合计联动    —— 页面上出现的合计数是否都用占位符写（防止改明细后不联动）
D  资源存在    —— 图片路径是否真实存在
E  占位符合法  —— {count} 之类占位符的键名是否有效
F  构建一致    —— index.html 是否与「数据 + 模板」一致
G  渲染一致    —— JS 渲染器与 Python 渲染器产物是否一致（有 node 才查）
H  SEO 文件    —— sitemap.xml / robots.txt / robots.host.txt 是否与当前域名一致

用法
----
  python tools/check_site.py              # 检查，有 ERROR 返回 1
  python tools/check_site.py --verbose    # 顺便打印 WARN 明细
  python tools/check_site.py --no-build   # 跳过构建类检查（改数据还没重建时用）
"""

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "content", "site.json")
TPL_PATH = os.path.join(ROOT, "tools", "template.html")
OUT_PATH = os.path.join(ROOT, "index.html")

DERIVED_KEYS = (
    "count", "signupGroups", "signupPeople", "awardGroups", "awardPeople",
    "rateByGroup", "rateByPeople", "memberCount", "memberRatio",
    "topAwardGroups", "topAwardPeople", "topAwardRatio",
    "awardNationalSum", "awardProvinceSum",
)

# 必填字段：路径 -> 期望类型（list / str / num）
REQUIRED = {
    "site.url": "str",
    "site.ogImage": "str",
    "site.logo": "str",
    "meta.title": "str",
    "meta.description": "str",
    "meta.keywords": "str",
    "meta.author": "str",
    "meta.themeColor": "str",
    "nav.brand": "str",
    "nav.links": "list",
    "hero.title": "str",
    "hero.slogan": "str",
    "hero.stats": "list",
    "sections.about.title": "str",
    "sections.about.lead": "str",
    "sections.about.pillars": "list",
    "sections.history.title": "str",
    "sections.history.columns": "list",
    "sections.org.title": "str",
    "sections.org.depts": "list",
    "sections.activity.title": "str",
    "sections.activity.items": "list",
    "sections.results.title": "str",
    "sections.results.rows": "list",
    "sections.honors.title": "str",
    "sections.honors.lead": "str",
    "sections.honors.kpis": "list",
    "sections.honors.groups": "list",
    "sections.honors.certs": "list",
    "sections.honors.awards": "list",
    "sections.honors.awardsNote": "str",
    "sections.member.title": "str",
    "sections.member.kpis": "list",
    "sections.member.figures": "list",
    "sections.news.title": "str",
    "sections.news.items": "list",
    "sections.news.notices": "list",
    "sections.join.title": "str",
    "sections.join.steps": "list",
    "sections.contact.title": "str",
    "sections.contact.cards": "list",
    "footer.brand": "str",
    "footer.copyright": "str",
}

# 合计联动约定：这些位置展示的是「由明细汇总出来的数」，
# 必须写成占位符，否则改明细后页面上的数字不会跟着变。
AGGREGATE_CONTRACT = [
    ("hero.stats[1].value", ["{count}"]),
    ("hero.stats[1].display", ["{count}"]),
    ("sections.history.lead", ["{count}"]),
    ("sections.results.caption", ["{count}"]),
    ("sections.results.summary[2].desc", ["{topAwardGroups}", "{topAwardPeople}", "{topAwardRatio}"]),
    ("sections.member.lead", ["{memberCount}"]),
    ("sections.member.kpis[3].label", ["{memberRatio}"]),
    ("sections.activity.items[0].desc", ["{count}"]),
    ("sections.activity.items[0].kpis[0].value", ["{count}"]),
    ("sections.activity.items[0].kpis[1].value", ["{signupPeople}"]),
    ("sections.activity.items[0].kpis[2].value", ["{rateByGroup}"]),
]


# ---------------------------------------------------------------- 工具

class Report:
    def __init__(self):
        self.errors = []
        self.warns = []
        self.oks = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warns.append(msg)

    def ok(self, msg):
        self.oks.append(msg)

    def summary(self):
        for m in self.oks:
            print(f"  [ok]   {m}")
        for m in self.warns:
            print(f"  [warn] {m}")
        for m in self.errors:
            print(f"  [ERR]  {m}")


def get_path(obj, path):
    """路径可含数组下标：hero.stats[1].value"""
    cur = obj
    for seg in path.split("."):
        m = re.match(r"^([^[]+)(?:\[(\d+)\])?$", seg)
        if not m:
            return None
        if not isinstance(cur, dict):
            return None
        cur = cur.get(m.group(1))
        if m.group(2) is not None:
            if not isinstance(cur, list):
                return None
            idx = int(m.group(2))
            cur = cur[idx] if idx < len(cur) else None
    return cur


def walk_strings(node, path=""):
    """遍历 JSON 树，产出 (路径, 字符串值)。"""
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from walk_strings(v, f"{path}.{k}" if path else k)


# ---------------------------------------------------------------- 检查项

def check_structure(data, rep):
    for path, kind in REQUIRED.items():
        val = get_path(data, path)
        if val is None:
            rep.error(f"A 结构：缺少必填字段 {path}")
            continue
        if kind == "list" and not isinstance(val, list):
            rep.error(f"A 结构：{path} 应为数组，实际是 {type(val).__name__}")
        elif kind == "str" and not isinstance(val, str):
            rep.error(f"A 结构：{path} 应为字符串，实际是 {type(val).__name__}")
    if not rep.errors:
        rep.ok(f"A 结构：{len(REQUIRED)} 个必填字段齐全")


def check_rows(data, rep):
    """明细自洽：获奖数不应超过报名数（3D 打印是已知的原件口径差，单独提示）。"""
    rows = get_path(data, "sections.results.rows") or []
    if not rows:
        rep.error("B 明细：sections.results.rows 为空")
        return
    for i, r in enumerate(rows):
        name = r.get("name", f"第 {i + 1} 项")
        for k in ("signupGroups", "signupPeople", "awardGroups", "awardPeople"):
            v = r.get(k)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                rep.error(f"B 明细：{name} 的 {k} 应为数字，实际是 {v!r}")
            elif v < 0:
                rep.error(f"B 明细：{name} 的 {k} 为负数（{v}）")
        if r.get("awardGroups", 0) > r.get("signupGroups", 0):
            rep.error(
                f"B 明细：{name} 获奖组数 {r.get('awardGroups')} > 报名组数 {r.get('signupGroups')}，"
                "请核对明细")
        if r.get("awardPeople", 0) > r.get("signupPeople", 0):
            rep.warn(
                f"B 明细：{name} 获奖人次 {r.get('awardPeople')} > 报名人次 {r.get('signupPeople')}"
                f"（差 {r.get('awardPeople') - r.get('signupPeople')} 人次）。"
                "这是报名表与获奖名单两份原件的口径差，页面已加脚注说明，请勿擅自改数。")
    if not any(m.startswith("B 明细") for m in rep.errors):
        rep.ok(f"B 明细：{len(rows)} 项赛事的报名/获奖数自洽")


def check_aggregate_contract(data, rep):
    """合计联动：约定位置必须用占位符，否则改明细后页面数字不联动。"""
    bad = 0
    for path, needed in AGGREGATE_CONTRACT:
        val = get_path(data, path)
        if not isinstance(val, str):
            rep.error(f"C 联动：{path} 不是字符串")
            bad += 1
            continue
        missing = [n for n in needed if n not in val]
        if missing:
            rep.error(
                f"C 联动：{path} 缺少占位符 {' '.join(missing)}。"
                "此处展示的是由明细汇总出来的数，必须用占位符写，改明细才会联动。")
            bad += 1
    if not bad:
        rep.ok(f"C 联动：{len(AGGREGATE_CONTRACT)} 处合计数都用占位符写")


def check_assets(data, rep):
    """资源存在：本地图片路径必须真的在仓库里。"""
    missing = []
    checked = 0
    for path, val in walk_strings(data):
        if not val or val.startswith(("http://", "https://", "data:", "#")):
            continue
        if not re.search(r"\.(png|jpe?g|gif|svg|webp|avif)$", val, re.I):
            continue
        checked += 1
        if not os.path.isfile(os.path.join(ROOT, val.replace("/", os.sep))):
            missing.append(f"{path} → {val}")
    for m in missing:
        rep.error(f"D 资源：{m} 指向的文件不存在")
    if not missing:
        rep.ok(f"D 资源：{checked} 个本地图片路径均存在")


def check_placeholders(data, rep):
    """占位符合法性：{xxx} 的键名必须是已知的派生值。

    数据与模板都要扫：模板里的 {key} 写错不会报错，而是原样穿到页面上，
    属于最容易漏掉的失败模式（例如把 {count} 写成 {cont}）。
    """
    pat = re.compile(r"\{([a-zA-Z][a-zA-Z0-9]*)\}")
    bad = []
    for path, val in walk_strings(data):
        for key in pat.findall(val):
            if key not in DERIVED_KEYS:
                bad.append(f"{path} → {{{key}}}")
    if os.path.isfile(TPL_PATH):
        with open(TPL_PATH, encoding="utf-8") as fh:
            tpl = fh.read()
        # 模板里有大量 {{...}}（mustache）与 CSS 的 {}，先剔除再找单层 {key}
        tpl_no_mustache = re.sub(r"\{\{.*?\}\}", " ", tpl, flags=re.S)
        tpl_no_css = re.sub(r"\{[^{}]*\}", lambda m: m.group(0)
                            if pat.fullmatch(m.group(0)) else " ", tpl_no_mustache)
        for key in pat.findall(tpl_no_css):
            if key not in DERIVED_KEYS:
                bad.append(f"tools/template.html → {{{key}}}")
    for b in bad:
        rep.error(f"E 占位符：{b} 不是有效的派生值键名")
    if not bad:
        rep.ok("E 占位符：数据与模板中的占位符键名均有效")


def check_build(rep):
    """构建一致：index.html 必须等于「数据 + 模板」的构建产物。"""
    if not os.path.isfile(OUT_PATH):
        rep.error("F 构建：缺少 index.html")
        return
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build.py"), "--check"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    if r.returncode != 0:
        rep.error("F 构建：index.html 与 content/site.json + tools/template.html 不一致，"
                  "请运行 python tools/build.py 重建")
    else:
        rep.ok("F 构建：index.html 与数据 + 模板一致")


def check_render(rep):
    """渲染一致：JS 渲染器（编辑器预览用）与 Python 渲染器产物必须一致。"""
    if not _has_node():
        rep.warn("G 渲染：未找到 node，跳过 JS 渲染器交叉校验")
        return
    r = subprocess.run(["node", os.path.join(ROOT, "tools", "render.js"), "--check"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    if r.returncode != 0:
        rep.error("G 渲染：tools/render.js 的产物与 index.html 不一致，"
                  "两个渲染器已出现分叉")
    else:
        rep.ok("G 渲染：JS 渲染器与 Python 渲染器产物一致")


def check_seo(data, rep):
    """SEO 文件：域名与 sitemap/robots 要和 site.url 对得上。"""
    url = (get_path(data, "site.url") or "").rstrip("/")
    if not url:
        rep.error("H SEO：site.url 为空")
        return
    sm_path = os.path.join(ROOT, "sitemap.xml")
    rb_path = os.path.join(ROOT, "robots.txt")
    hr_path = os.path.join(ROOT, "robots.host.txt")

    if not os.path.isfile(sm_path):
        rep.error("H SEO：缺少 sitemap.xml")
    else:
        sm = open(sm_path, encoding="utf-8").read()
        if url not in sm:
            rep.error(f"H SEO：sitemap.xml 里没有当前站点地址 {url}，请运行 python tools/gen_seo.py")
        else:
            rep.ok("H SEO：sitemap.xml 与当前域名一致")

    if not os.path.isfile(rb_path):
        rep.error("H SEO：缺少 robots.txt")
    else:
        rb = open(rb_path, encoding="utf-8").read()
        if f"Sitemap: {url}/sitemap.xml" not in rb:
            rep.error(f"H SEO：robots.txt 的 Sitemap 行与 {url} 不一致，请运行 python tools/gen_seo.py")
        else:
            rep.ok("H SEO：robots.txt 与当前域名一致")

    prefix = ""
    rest = url.split("://", 1)[-1]
    if "/" in rest:
        p = rest.split("/", 1)[1].strip("/")
        prefix = "/" + p if p else ""
    if prefix:
        if not os.path.isfile(hr_path):
            rep.error(f"H SEO：站点部署在子路径 {prefix}，缺少 robots.host.txt"
                      "（主机根目录版），请运行 python tools/gen_seo.py")
        else:
            hr = open(hr_path, encoding="utf-8").read()
            if f"Disallow: {prefix}/editor.html" not in hr:
                rep.error(f"H SEO：robots.host.txt 的路径前缀不是 {prefix}，请运行 python tools/gen_seo.py")
            else:
                rep.ok(f"H SEO：robots.host.txt 已按子路径 {prefix} 生成")


def _has_node():
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=20)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


# ---------------------------------------------------------------- 主流程

def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="站点一致性检查")
    ap.add_argument("--verbose", action="store_true", help="打印 WARN 明细")
    ap.add_argument("--no-build", action="store_true", help="跳过构建与渲染检查")
    ap.add_argument("--skip-seo", action="store_true", help="跳过 sitemap / robots 检查")
    ap.add_argument("--noop", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if not os.path.isfile(DATA_PATH):
        print(f"[错误] 找不到 {DATA_PATH}", file=sys.stderr)
        return 2

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    rep = Report()
    check_structure(data, rep)
    check_rows(data, rep)
    check_aggregate_contract(data, rep)
    check_assets(data, rep)
    check_placeholders(data, rep)
    if not args.no_build:
        check_build(rep)
        check_render(rep)
    if not args.skip_seo:
        check_seo(data, rep)

    print("站点一致性检查")
    print("=" * 46)
    rep.summary()
    print("=" * 46)
    print(f"通过 {len(rep.oks)} 项，警告 {len(rep.warns)} 项，错误 {len(rep.errors)} 项")
    if rep.errors:
        print("\n有错误，请先修复再提交。")
        return 1
    if rep.warns and not args.verbose:
        print("（有警告，加 --verbose 查看明细）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
