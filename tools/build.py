#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 content/site.json + tools/template.html 构建 index.html。

    python tools/build.py           生成 index.html
    python tools/build.py --check   只构建并与现有 index.html 比对，不写盘

模板语法（迷你 mustache）：
    {{path}}            取值并转义
    {{$path}}           取值且不转义（$ 命名空间存放构建期生成的原始 HTML）
    {{#path}}…{{/path}}  区块：列表→逐项迭代，字典→压栈，字符串/布尔→条件
    {{^path}}…{{/path}}  反向区块
    占位符 {key}        会被派生值（合计、获奖率等）替换
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "content", "site.json")
TPL_PATH = os.path.join(ROOT, "tools", "template.html")
OUT_PATH = os.path.join(ROOT, "index.html")

MISSING = object()

# ---------------------------------------------------------------- 模板引擎


def scan(tpl):
    """把模板切成 text / var / sec / inv / close 记号。"""
    out = []
    pos = 0
    while True:
        start = tpl.find("{{", pos)
        if start < 0:
            out.append(("text", tpl[pos:]))
            return out
        if start > pos:
            out.append(("text", tpl[pos:start]))
        end = tpl.find("}}", start)
        if end < 0:
            raise ValueError("模板中存在未闭合的 {{")
        inner = tpl[start + 2:end].strip()
        pos = end + 2
        if inner.startswith("#"):
            out.append(("sec", inner[1:].strip()))
        elif inner.startswith("^"):
            out.append(("inv", inner[1:].strip()))
        elif inner.startswith("/"):
            out.append(("close", inner[1:].strip()))
        else:
            out.append(("var", inner))


def parse(toks, pos, stop):
    nodes = []
    while pos < len(toks):
        kind = toks[pos][0]
        if kind in ("text", "var"):
            nodes.append((kind, toks[pos][1]))
            pos += 1
        elif kind in ("sec", "inv"):
            name = toks[pos][1]
            body, pos = parse(toks, pos + 1, stop + (name,))
            nodes.append((kind, name, body))
        else:
            name = toks[pos][1]
            if name in stop:
                return nodes, pos + 1
            raise ValueError("模板中出现未匹配的 {{/%s}}" % name)
    return nodes, pos


def resolve(frame, parts):
    cur = frame
    for part in parts:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return MISSING
    return cur


def lookup(ctx, path):
    """按 mustache 规则在上下文栈里找路径：先整条路径，再退到最长公共前缀。"""
    if path.startswith("$"):
        return resolve(ctx[0].get("$", {}), path[1:].split("."))
    parts = path.split(".")
    for frame in reversed(ctx):
        val = resolve(frame, parts)
        if val is not MISSING:
            return val
    for frame in reversed(ctx):
        for i in range(len(parts) - 1, 0, -1):
            val = resolve(frame, parts[:i])
            if val is not MISSING:
                rest = resolve(val, parts[i:])
                return val if rest is MISSING else rest
    return ""


ENTITY_RE = re.compile(r"&(?:#\d+|#[xX][0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]*);")


def escape(text):
    """转义 & < > "，但保留已有的实体引用（&ensp; &amp; …）不被二次转义。"""
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    out = []
    last = 0
    for match in ENTITY_RE.finditer(text):
        out.append(escape_plain(text[last:match.start()]))
        out.append(match.group(0))
        last = match.end()
    out.append(escape_plain(text[last:]))
    return "".join(out)


def escape_plain(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def render(nodes, ctx):
    out = []
    for node in nodes:
        kind = node[0]
        if kind == "text":
            out.append(node[1])
        elif kind == "var":
            path = node[1]
            val = lookup(ctx, path)
            out.append(str(val) if path.startswith("$") else escape(val))
        elif kind == "sec":
            val = lookup(ctx, node[1])
            if isinstance(val, list):
                for item in val:
                    out.append(render(node[2], ctx + [item]))
            elif isinstance(val, dict):
                out.append(render(node[2], ctx + [val]))
            elif val:
                out.append(render(node[2], ctx))
        elif kind == "inv":
            val = lookup(ctx, node[1])
            if not val:
                out.append(render(node[2], ctx))
    return "".join(out)


# ---------------------------------------------------------------- 派生值

DERIVED_KEYS = ("count", "signupGroups", "signupPeople", "awardGroups",
                "awardPeople", "rateByGroup", "rateByPeople",
                "memberCount", "memberRatio", "topAwardGroups",
                "topAwardPeople", "topAwardRatio",
                "awardNationalSum", "awardProvinceSum")


def derive(data):
    """从明细数据算出合计与比率，页面上的所有合计数都来自这里。"""
    rows = data["sections"]["results"]["rows"]
    signup_groups = sum(r["signupGroups"] for r in rows)
    signup_people = sum(r["signupPeople"] for r in rows)
    award_groups = sum(r["awardGroups"] for r in rows)
    award_people = sum(r["awardPeople"] for r in rows)
    member = data["sections"]["member"]["kpis"]
    member_count = int(member[0]["value"])
    member_from = int(member[3]["value"])
    top = max(rows, key=lambda r: r["awardPeople"])
    history_awards = data["sections"]["honors"]["awards"]
    return {
        "count": str(len(rows)),
        "signupGroups": str(signup_groups),
        "signupPeople": str(signup_people),
        "awardGroups": str(award_groups),
        "awardPeople": str(award_people),
        "rateByGroup": "%.1f" % (award_groups * 100.0 / signup_groups),
        "rateByPeople": "%.1f" % (award_people * 100.0 / signup_people),
        "memberCount": str(member_count),
        "memberRatio": "%.1f" % (member_from * 100.0 / member_count),
        "topAwardGroups": str(top["awardGroups"]),
        "topAwardPeople": str(top["awardPeople"]),
        "topAwardRatio": "%.1f" % (top["awardPeople"] * 100.0 / award_people),
        "awardNationalSum": str(sum(a["national"] for a in history_awards)),
        "awardProvinceSum": str(sum(a["province"] for a in history_awards)),
    }


PLACEHOLDER_RE = re.compile(r"\{(" + "|".join(DERIVED_KEYS) + r")\}")


def expand(node, derived):
    """把 {count} 这类占位符替换成派生值。"""
    if isinstance(node, str):
        return PLACEHOLDER_RE.sub(lambda m: derived[m.group(1)], node)
    if isinstance(node, list):
        return [expand(v, derived) for v in node]
    if isinstance(node, dict):
        return dict((k, expand(v, derived)) for k, v in node.items())
    return node


# ---------------------------------------------------------------- 构件

def build_head(data):
    site = data["site"]
    meta = data["meta"]
    url = site["url"]
    logo = url + site["logo"]
    attr = escape

    def js(value):
        return json.dumps(value, ensure_ascii=False)

    lines = [
        "<title>%s</title>" % attr(meta["title"]),
        '<meta name="description" content="%s">' % attr(meta["description"]),
        '<meta name="keywords" content="%s">' % attr(meta["keywords"]),
        '<meta property="og:title" content="%s">' % attr(meta["ogTitle"]),
        '<meta property="og:description" content="%s">' % attr(meta["ogDescription"]),
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="%s">' % attr(meta["siteName"]),
        '<meta property="og:locale" content="zh_CN">',
        '<meta property="og:url" content="%s">' % attr(url),
        '<meta property="og:image" content="%s">' % attr(site["ogImage"]),
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:image:alt" content="%s">' % attr(meta["ogImageAlt"]),
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:title" content="%s">' % attr(meta["ogTitle"]),
        '<meta name="twitter:description" content="%s">' % attr(meta["ogDescription"]),
        '<meta name="twitter:image" content="%s">' % attr(site["ogImage"]),
        '<meta name="robots" content="index,follow,max-image-preview:large">',
        '<meta name="author" content="%s">' % attr(meta["author"]),
        '<meta name="theme-color" content="%s">' % attr(meta["themeColor"]),
        '<link rel="canonical" href="%s">' % attr(url),
        '<script type="application/ld+json">',
        "{",
        '  "@context": "https://schema.org",',
        '  "@graph": [',
        "    {",
        '      "@type": "Organization",',
        '      "@id": %s,' % js(url + "#org"),
        '      "name": "重庆工商大学科技协会",',
        '      "alternateName": [%s],' % ", ".join(
            js(n) for n in meta["alternateNames"]),
        '      "url": %s,' % js(url),
        '      "logo": %s,' % js(logo),
        '      "description": %s,' % js(meta["orgDescription"]),
        '      "foundingDate": "2002",',
        '      "parentOrganization": { "@type": "CollegeOrUniversity", "name": %s },'
        % js(meta["parentOrg"]),
        '      "address": {',
        '        "@type": "PostalAddress",',
        '        "addressCountry": "CN",',
        '        "addressRegion": "重庆市",',
        '        "streetAddress": %s' % js(meta["orgAddress"]),
        "      },",
        '      "contactPoint": [{',
        '        "@type": "ContactPoint",',
        '        "contactType": "招新咨询",',
        '        "telephone": %s,' % js(meta["telephone"]),
        '        "availableLanguage": ["zh-CN"]',
        "      }]",
        "    },",
        "    {",
        '      "@type": "WebSite",',
        '      "@id": %s,' % js(url + "#website"),
        '      "name": "重庆工商大学科技协会官网",',
        '      "url": %s,' % js(url),
        '      "inLanguage": "zh-CN",',
        '      "publisher": { "@id": %s }' % js(url + "#org"),
        "    }",
        "  ]",
        "}",
        "</script>",
    ]
    return "\n".join(lines)


def build_nav_mob(nav):
    """移动端菜单：与桌面端共用同一份链接数据。"""
    out = ["\n"]
    for link in nav["links"]:
        out.append('      <a href="%s">%s</a>\n'
                   % (escape(link["href"]), escape(link["text"])))
    out.append('      <a class="nav-cta" href="%s">%s</a>\n    '
                % (escape(nav["cta"]["href"]), escape(nav["cta"]["text"])))
    return "".join(out)


def build_results_kpis(derived):
    return (
        "\n"
        '      <div class="kpi"><b>{count}<i> 项</i></b><span>赛事项目</span></div>\n'
        '      <div class="kpi"><b data-c="{signupPeople}">{signupPeople}</b>'
        '<span>报名人次（{signupGroups} 组）</span></div>\n'
        '      <div class="kpi"><b data-c="{awardPeople}">{awardPeople}</b>'
        '<span>获奖人次（{awardGroups} 组）</span></div>\n'
        '      <div class="kpi"><b data-c="{rateByPeople}" data-suffix="%">'
        '{rateByPeople}%</b><span>获奖率（按人次）</span></div>\n'
        "    "
    ).format(**derived)


def build_results_noscript(derived):
    return (
        "<noscript>\n"
        '          <tr>\n'
        '            <td colspan="6" style="font-size:13px;color:var(--sub);line-height:1.8">\n'
        "              本表的{count} 项赛事明细由脚本渲染，当前浏览器已禁用 JavaScript，因此无法显示。\n"
        "              合计数据为：报名 {signupGroups} 组／{signupPeople} 人次，"
        "获奖 {awardGroups} 组／{awardPeople} 人次，组获奖率 {rateByGroup}%。\n"
        "              启用 JavaScript 即可查看完整明细；也可联系协会获取《科创月统计表》原件。\n"
        "            </td>\n"
        "          </tr>\n"
        "        </noscript>"
    ).format(**derived)


def build_results_tfoot(derived):
    return (
        "\n"
        "          <tr>\n"
        '            <td scope="row">合计（{count} 项）</td>\n'
        '            <td class="n">{signupGroups}</td>\n'
        '            <td class="n">{signupPeople}</td>\n'
        '            <td class="n">{awardGroups}</td>\n'
        '            <td class="n">{awardPeople}</td>\n'
        '            <td class="n">{rateByGroup}%</td>\n'
        "          </tr>\n"
        "        "
    ).format(**derived)


def build_results_js(rows):
    """赛事明细表：由 rows 生成，获奖率按 获奖组 ÷ 报名组 计算。"""
    lines = []
    for row in rows:
        rate = row["awardGroups"] * 100.0 / row["signupGroups"]
        lines.append("[%s,%d,%d,%d,%d,%.1f]" % (
            json.dumps(row["name"], ensure_ascii=False),
            row["signupGroups"], row["signupPeople"],
            row["awardGroups"], row["awardPeople"], rate))
    return "var RESULTS=[\n" + ",\n".join(lines) + "];"


# ---------------------------------------------------------------- 主流程

def add_has_flags(node):
    """给每个含列表的字典补一个 has<Key> 布尔量，供模板做条件判断。"""
    if isinstance(node, dict):
        for key in list(node):
            val = node[key]
            if isinstance(val, list):
                node["has" + key[0].upper() + key[1:]] = bool(val)
                for item in val:
                    add_has_flags(item)
            else:
                add_has_flags(val)
    elif isinstance(node, list):
        for item in node:
            add_has_flags(item)
    return node


def build():
    with open(DATA_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    with open(TPL_PATH, encoding="utf-8") as fh:
        template = fh.read()

    derived = derive(data)
    data = expand(data, derived)
    add_has_flags(data)

    data["$"] = {
        "head": build_head(data),
        "nav": {"mob": build_nav_mob(data["nav"])},
        "results": {
            "kpis": build_results_kpis(derived),
            "noscript": build_results_noscript(derived),
            "tfoot": build_results_tfoot(derived),
            "js": build_results_js(data["sections"]["results"]["rows"]),
        },
    }

    toks = scan(template)
    nodes, _ = parse(toks, 0, ())
    # 渲染后再展开一次：数据层在渲染前已展开，但模板里直接写的 {key}
    # （例如表格合计行）只有在这一步才会被替换，否则会原样穿到页面上。
    return expand(render(nodes, [data]), derived)


def main():
    # Windows 控制台默认 GBK，输出中文会抛 UnicodeEncodeError
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="构建 index.html")
    ap.add_argument("--check", action="store_true",
                    help="只构建并与现有 index.html 比对，不写盘")
    args = ap.parse_args()

    html = build()
    if args.check:
        if not os.path.exists(OUT_PATH):
            print("缺少 index.html，无法比对")
            return 1
        with open(OUT_PATH, encoding="utf-8") as fh:
            current = fh.read()
        if current == html:
            print("index.html 与构建产物一致")
            return 0
        print("index.html 与构建产物不一致")
        return 1

    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print("index.html: %d bytes" % os.path.getsize(OUT_PATH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
