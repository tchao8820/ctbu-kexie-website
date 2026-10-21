#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTBU-STA 官网 · SEO 文件生成器
================================
自动扫描站点发布根目录，生成：
  1) sitemap.xml     —— 收录全部公开页面（loc / lastmod / changefreq / priority）
  2) robots.txt      —— 站点根目录的 robots（允许主流搜索引擎抓取，声明 sitemap）
  3) robots.host.txt —— 主机根目录的 robots（把上一步的路径加上站点子路径前缀）

为什么要两份 robots
------------------
搜索引擎只认「主机根目录」的 robots.txt。本站部署在
https://tchao8820.github.io/ctbu-kexie-website/ 这种子路径下，
仓库里的 robots.txt 实际被访问到的是
https://tchao8820.github.io/ctbu-kexie-website/robots.txt —— 搜索引擎不读它。
真正生效的那份要放在 https://tchao8820.github.io/robots.txt，
里面每条路径都得带上 /ctbu-kexie-website/ 前缀。
本脚本一次生成两份，前缀自动推算，不用手工维护两套规则。

设计要点
--------
* 「自动收录」：不写死页面清单，而是遍历发布根目录真实存在的 .html 文件，
  因此以后新增页面只需重跑本脚本即可。
* lastmod 取值优先级：Git 最后一次提交时间 > 文件 mtime。
* sitemap 中不出现被 robots.txt 屏蔽的 URL（否则搜索引擎会报「已屏蔽但仍提交」）。
* sitemap 中不出现带 # 的锚点 URL：本站是单页站点，锚点是页内导航，
  不构成独立可索引页面（Google 明确要求 sitemap 中的 URL 不含 fragment）。

用法
----
  python gen_seo.py                                   # 用默认站点地址
  python gen_seo.py --site-url https://kexie.ctbu.edu.cn   # 绑定自定义域名后重跑
  python gen_seo.py --root .. --dry-run               # 只预览不落盘
"""

import argparse
import datetime as dt
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------- 默认配置

DEFAULT_SITE = "https://tchao8820.github.io/ctbu-kexie-website"

# 扫描时跳过的目录（构建产物 / 源码 / 版本库 / 工具脚本）
SKIP_DIRS = {
    ".git", ".github", ".workbuddy",
    "node_modules", "dist", "build", "out", "_site", ".cache",
    "assets", "tools", "src", "scripts", "content",
}

# 明确排除的文件（无实际内容，或已由 robots.txt 屏蔽）
SKIP_FILES = {
    "404.html",
    "template.html",
    "index.template.html",
    "editor.html",# 临时在线编辑器，不应被搜索引擎收录
}

# robots.txt 屏蔽规则（顺序即输出顺序）
# 注意：不要屏蔽 /assets/ —— 那是站点真实使用的图片目录，
#       屏蔽后 og:image 与正文配图将无法被抓取，影响图片搜索收录。
DISALLOW = [
    "/404.html",          # 错误页，无内容
    "/editor.html",       # 临时在线编辑器，不应对外收录
    "/tools/",            # 生成脚本（.py，无索引价值）
    "/dist/",             # 构建产物目录
    "/build/",            # 构建产物目录
    "/node_modules/",     # 依赖目录
    "/*.json$",           # 数据文件
    "/*.md$",             # 源文档
    "/*.map$",            # sourcemap
    "/*.log$",            # 日志
]

# 主流搜索引擎（仅作注释说明，robots 用 User-agent: * 统一覆盖）
MAJOR_CRAWLERS = [
    "Googlebot（谷歌）", "Baiduspider（百度）", "Bingbot（必应）",
    "Sogou web spider（搜狗）", "360Spider（360 搜索）",
    "YandexBot（俄罗斯）", "DuckDuckBot", "Applebot",
]


def norm_base(url: str) -> str:
    """规范化站点根地址：去尾部斜杠，补 https。"""
    u = (url or "").strip()
    if not u:
        return DEFAULT_SITE.rstrip("/")
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u.rstrip("/")


def site_path(base: str) -> str:
    """取出站点根地址里的路径部分（子路径部署时形如 /ctbu-kexie-website）。"""
    rest = base.split("://", 1)[-1]
    if "/" not in rest:
        return ""
    p = rest.split("/", 1)[1].strip("/")
    return "/" + p if p else ""


def git_lastmod(root: str, rel: str) -> str | None:
    """取文件在 Git 中最后一次提交的 ISO 时间；失败返回 None。"""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", rel],
            cwd=root, capture_output=True, text=True, timeout=20,
        )
        if out.returncode == 0 and out.stdout.strip():
            s = out.stdout.strip().splitlines()[0].strip()
            # 归一为 YYYY-MM-DD（日期粒度足够，且避免时区噪音）
            return dt.datetime.fromisoformat(s).astimezone(dt.timezone.utc).date().isoformat()
    except Exception:
        pass
    return None


def fs_lastmod(path: str) -> str:
    ts = os.path.getmtime(path)
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()


def collect_pages(root: str):
    """遍历发布根目录，收集公开页面。返回 [(url_path, abs_path, lastmod, depth)]"""
    pages, skipped = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]

        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
        rel_dir = "" if rel_dir == "." else rel_dir

        for fn in sorted(filenames):
            if not fn.lower().endswith((".html", ".htm")):
                continue
            if fn in SKIP_FILES or fn.startswith("."):
                skipped.append((rel_dir, fn, "显式排除"))
                continue

            rel = (f"{rel_dir}/{fn}" if rel_dir else fn)
            abs_p = os.path.join(dirpath, fn)

            # URL 路径：index.html → 目录根
            if fn.lower() == "index.html":
                url_path = "/" + (rel_dir + "/" if rel_dir else "")
            else:
                url_path = "/" + rel

            depth = 0 if url_path.rstrip("/") == "" else url_path.strip("/").count("/") + 1
            lastmod = git_lastmod(root, rel) or fs_lastmod(abs_p)
            pages.append((url_path, abs_p, lastmod, depth))

    # 排序：根目录优先，其次按路径
    pages.sort(key=lambda x: (x[3], x[0]))
    return pages, skipped


def decide_meta(url_path: str, depth: int):
    """按页面重要度给出 changefreq / priority。"""
    if depth == 0:
        return "weekly", "1.0"
    if depth == 1:
        return "monthly", "0.8"
    return "monthly", "0.6"


def build_sitemap(base: str, pages) -> str:
    urlset = ET.Element("urlset", {
        "xmlns": "http://www.sitemap.org/schemas/sitemap/0.9",
        "xmlns:xhtml": "http://www.w3.org/1999/xhtml",
    })
    for url_path, _abs, lastmod, depth in pages:
        u = ET.SubElement(urlset, "url")
        ET.SubElement(u, "loc").text = base + url_path
        ET.SubElement(u, "lastmod").text = lastmod
        cf, pr = decide_meta(url_path, depth)
        ET.SubElement(u, "changefreq").text = cf
        ET.SubElement(u, "priority").text = pr

    ET.indent(urlset, space="  ", level=0)
    body = ET.tostring(urlset, encoding="unicode")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- CTBU-STA 官网站点地图 · 由 tools/gen_seo.py 自动生成，请勿手工编辑 -->\n"
        + body + "\n"
    )


def build_robots(base: str, sitemap_url: str) -> str:
    lines = [
        "# CTBU-STA 官网 robots.txt · 由 tools/gen_seo.py 自动生成",
        "# 适用搜索引擎：" + "、".join(MAJOR_CRAWLERS),
        "# （User-agent: * 为通配规则，覆盖上表全部主流爬虫）",
        "",
        "User-agent: *",
        "Allow: /",
        "",
        "# 屏蔽无实际内容的路径",
    ]
    lines += [f"Disallow: {d}" for d in DISALLOW]
    lines += [
        "",
        "# 站点地图",
        f"Sitemap: {sitemap_url}",
        "",
    ]
    return "\n".join(lines)


def build_host_robots(base: str, sitemap_url: str) -> str:
    """主机根目录用的 robots：站点根地址的路径部分变成每条规则的前缀。

    站点部署在 https://host/ctbu-kexie-website/ 时，仓库里的 robots.txt
    实际位于 https://host/ctbu-kexie-website/robots.txt，搜索引擎不读；
    真正生效的是 https://host/robots.txt，那份的路径必须带子路径前缀。
    """
    prefix = site_path(base)
    lines = [
        "# CTBU-STA 官网 robots.txt · 主机根目录版 · 由 tools/gen_seo.py 自动生成",
        "# 部署于子路径 " + (prefix or "/") + " 下，搜索引擎只认主机根目录的 robots.txt。",
        "# 请把本文件放到主机根目录（GitHub 用户站仓库根目录 / 自定义域名根目录）。",
        "# 适用搜索引擎：" + "、".join(MAJOR_CRAWLERS),
        "",
        "User-agent: *",
        f"Allow: {prefix + '/' if prefix else '/'}",
        "",
        "# 屏蔽无实际内容的路径",
    ]
    lines += [f"Disallow: {prefix}{d}" for d in DISALLOW]
    lines += [
        "",
        "# 站点地图",
        f"Sitemap: {sitemap_url}",
        "",
    ]
    return "\n".join(lines)


def main():
    # Windows 控制台默认 GBK，输出 ✓ 等字符会抛 UnicodeEncodeError
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="生成 sitemap.xml 与 robots.txt")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    help="站点发布根目录（默认：本脚本所在目录的上一级）")
    ap.add_argument("--site-url", default=os.environ.get("SITE_URL", DEFAULT_SITE),
                    help="站点根地址，如 https://tchao8820.github.io/ctbu-kexie-website")
    ap.add_argument("--dry-run", action="store_true", help="只打印预览，不写文件")
    ap.add_argument("--host-robots", default=None,
                    help="主机根目录 robots.txt 的写出路径（默认 <root>/robots.host.txt）")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    base = norm_base(args.site_url)
    sitemap_url = base + "/sitemap.xml"
    host_robots_path = os.path.abspath(args.host_robots) if args.host_robots else os.path.join(root, "robots.host.txt")

    if not os.path.isdir(root):
        print(f"[错误] 发布根目录不存在：{root}", file=sys.stderr)
        return 2

    pages, skipped = collect_pages(root)
    if not pages:
        print("[错误] 未发现任何公开页面，请检查 --root 是否正确", file=sys.stderr)
        return 3

    sm = build_sitemap(base, pages)
    rb = build_robots(base, sitemap_url)
    hrb = build_host_robots(base, sitemap_url)

    print(f"站点根地址 : {base}")
    print(f"发布根目录 : {root}")
    print(f"收录页面   : {len(pages)} 个")
    for url_path, abs_p, lastmod, depth in pages:
        cf, pr = decide_meta(url_path, depth)
        print(f"   ✓ {base + url_path:<52} lastmod={lastmod}  {cf}/{pr}")
    if skipped:
        print(f"已排除     : {len(skipped)} 个")
        for d, fn, why in skipped:
            print(f"   × /{(d + '/' + fn) if d else fn}  ({why})")

    if args.dry_run:
        print("\n----- sitemap.xml -----")
        print(sm)
        print("----- robots.txt -----")
        print(rb)
        print("----- robots.host.txt -----")
        print(hrb)
        return 0

    p_sm = os.path.join(root, "sitemap.xml")
    p_rb = os.path.join(root, "robots.txt")
    for path, text in ((p_sm, sm), (p_rb, rb), (host_robots_path, hrb)):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"已写出：{path}（{os.path.getsize(path)} 字节）")

    if site_path(base):
        print(f"\n提示：站点位于子路径 {site_path(base)}，仓库内的 robots.txt 搜索引擎不读；")
        print(f"      请把 {host_robots_path} 放到主机根目录。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
