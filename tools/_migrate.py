#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性迁移脚本：index.html → content/site.json + tools/template.html

做法：用带源码偏移的 HTML 解析器定位每个可编辑节点，
把节点内容替换成 {{占位符}}，同时把原值写进 site.json。

跑完即完成内容层抽取；此后 site.json + template.html 是唯一真源，
index.html 由 tools/build.py 生成，本脚本不再参与日常流程。
"""
import json
import os
import re
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "index.html")

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}


# ----------------------------------------------------------------- 解析器

class El:
    __slots__ = ("tag", "attrs", "start", "cstart", "cend", "end",
                 "parent", "children", "texts")

    def __init__(self, tag, attrs, start, cstart, cend, end, parent):
        self.tag = tag
        self.attrs = attrs
        self.start = start
        self.cstart = cstart
        self.cend = cend
        self.end = end
        self.parent = parent
        self.children = []
        self.texts = []

    @property
    def classes(self):
        return (self.attrs.get("class") or "").split()


class Parser(HTMLParser):
    def __init__(self, src):
        super().__init__(convert_charrefs=False)
        self.src = src
        self.line_starts = [0]
        for i, ch in enumerate(src):
            if ch == "\n":
                self.line_starts.append(i + 1)
        self.root = El("#root", {}, 0, 0, len(src), len(src), None)
        self.stack = [self.root]

    def off(self):
        line, col = self.getpos()
        return self.line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        start = self.off()
        raw = self.get_starttag_text()
        el = El(tag, {k: (v if v is not None else "") for k, v in attrs},
                start, start + len(raw), start + len(raw), start + len(raw),
                self.stack[-1])
        self.stack[-1].children.append(el)
        if tag not in VOID:
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        start = self.off()
        raw = self.get_starttag_text()
        el = El(tag, {k: (v if v is not None else "") for k, v in attrs},
                start, start + len(raw), start + len(raw), start + len(raw),
                self.stack[-1])
        self.stack[-1].children.append(el)

    def handle_endtag(self, tag):
        start = self.off()
        close = self.src.find(">", start)
        end = len(self.src) if close < 0 else close + 1
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                el = self.stack[i]
                el.cend = start
                el.end = end
                del self.stack[i:]
                return

    def handle_data(self, data):
        if not data:
            return
        start = self.off()
        self.stack[-1].texts.append((start, start + len(data), "text"))

    def handle_entityref(self, name):
        raw = "&%s;" % name
        start = self.off()
        self.stack[-1].texts.append((start, start + len(raw), "entity"))

    def handle_charref(self, name):
        raw = "&#%s;" % name
        start = self.off()
        self.stack[-1].texts.append((start, start + len(raw), "entity"))


def walk(el):
    for c in el.children:
        yield c
        yield from walk(c)


# ----------------------------------------------------------------- 选择器

PART_RE = re.compile(
    r"^(?P<tag>[a-zA-Z][\w-]*)?(?P<rest>(?:[#.][\w-]+)*)"
    r"(?::(?P<pseudo>[\w-]+)(?:\((?P<arg>[^)]*)\))?)?$")


def parse_part(p):
    if p == "*":
        return {"tag": "*", "id": None, "cls": [], "pseudo": None, "arg": None}
    m = PART_RE.match(p)
    if not m:
        raise ValueError("bad selector part: " + p)
    ids = re.findall(r"#([\w-]+)", m.group("rest"))
    cls = re.findall(r"\.([\w-]+)", m.group("rest"))
    return {
        "tag": m.group("tag"),
        "id": ids[0] if ids else None,
        "cls": cls,
        "pseudo": m.group("pseudo"),
        "arg": m.group("arg"),
    }


def match_part(el, part):
    if part["tag"] and part["tag"] != "*" and el.tag != part["tag"]:
        return False
    if part["id"] and el.attrs.get("id") != part["id"]:
        return False
    if part["cls"]:
        have = el.classes
        if not all(c in have for c in part["cls"]):
            return False
    if part["pseudo"]:
        sib = list(el.parent.children) if el.parent else []
        if part["pseudo"] == "nth-child":
            if sib.index(el) + 1 != int(part["arg"]):
                return False
        elif part["pseudo"] == "nth-of-type":
            same = [x for x in sib if x.tag == el.tag]
            if same.index(el) + 1 != int(part["arg"]):
                return False
        elif part["pseudo"] == "last-child":
            if not sib or sib[-1] is not el:
                return False
        else:
            raise ValueError("unsupported pseudo: " + part["pseudo"])
    return True


def tokenize(sel):
    toks = []
    for part in sel.split():
        if part == ">":
            toks.append((">", None))
        else:
            toks.append((" ", parse_part(part)))
    return toks


def select(root, sel):
    toks = tokenize(sel)
    cur = [root]
    comb = " "
    for kind, part in toks:
        if kind == ">":
            comb = ">"
            continue
        nxt = []
        for anc in cur:
            cand = list(anc.children) if comb == ">" else list(walk(anc))
            for el in cand:
                if match_part(el, part):
                    nxt.append(el)
        cur = []
        seen = set()
        for el in nxt:
            if id(el) not in seen:
                seen.add(id(el))
                cur.append(el)
        comb = " "
    return cur


def one(root, sel, index=0):
    hits = select(root, sel)
    if len(hits) <= index:
        raise LookupError("selector not found: %s [%d]" % (sel, index))
    return hits[index]


# ----------------------------------------------------------------- 编辑

class Edit:
    __slots__ = ("start", "end", "new")

    def __init__(self, start, end, new):
        self.start = start
        self.end = end
        self.new = new


def apply_edits(src, edits):
    edits = sorted(edits, key=lambda e: (e.start, e.end))
    prev_end = -1
    for e in edits:
        if e.start < prev_end:
            raise ValueError("overlapping edits: %d < %d" % (e.start, prev_end))
        prev_end = e.end
    out = []
    pos = 0
    for e in edits:
        out.append(src[pos:e.start])
        out.append(e.new)
        pos = e.end
    out.append(src[pos:])
    return "".join(out)


def find_attr_span(src, el, attr):
    """返回属性在源码中的位置。

    full_start/full_end 覆盖「空白 + name="value」整段；
    val_start/val_end 只覆盖引号内的值。
    """
    tag = src[el.start:el.cstart]
    m = re.search(r"(\s+)" + re.escape(attr) + r'\s*=\s*"([^"]*)"', tag)
    if not m:
        return None
    full_s = el.start + m.start(0)
    full_e = el.start + m.end(0)
    v_s = el.start + m.start(2)
    v_e = el.start + m.end(2)
    return (full_s, full_e, v_s, v_e, m.group(2))


def textish(el):
    """元素内的文本/实体节点，按出现顺序返回 (start, end, kind)。"""
    return sorted(el.texts, key=lambda t: t[0])


def inner_span(src, el):
    """元素的纯文本内部范围；元素内不得含子元素。"""
    if el.children:
        raise ValueError("inner has element children: <%s>" % el.tag)
    kids = textish(el)
    if not kids:
        raise ValueError("inner has no text: <%s>" % el.tag)
    return kids[0][0], kids[-1][1]


def split_ws(text):
    lead = text[:len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    return lead, text.strip(), trail


def leading_ws(src, pos):
    """pos 之前紧邻的空白串。"""
    i = pos
    while i > 0 and src[i - 1] in " \t\r\n":
        i -= 1
    return src[i:pos]


def set_path(obj, path, value):
    parts = path.split(".")
    cur = obj
    for i, p in enumerate(parts):
        last = i == len(parts) - 1
        nxt_digit = (not last) and parts[i + 1].isdigit()
        if p.isdigit():
            idx = int(p)
            while len(cur) <= idx:
                cur.append({})
            if last:
                cur[idx] = value
            else:
                if not isinstance(cur[idx], (dict, list)):
                    cur[idx] = [] if nxt_digit else {}
                cur = cur[idx]
        else:
            if last:
                cur[p] = value
            else:
                want = [] if nxt_digit else {}
                if p not in cur or not isinstance(cur[p], (dict, list)):
                    cur[p] = want
                cur = cur[p]


# ----------------------------------------------------------------- 字段

def resolve_field(item, f):
    sel = f["sel"]
    if sel == "$self":
        return item
    els = select(item, sel)
    idx = f.get("idx", 0)
    return els[idx] if len(els) > idx else None


def field_value(src, el, f, item=None):
    """抽出字段值并返回编辑列表（绝对偏移）。"""
    kind = f["kind"]
    path = f["path"]

    if kind == "inner":
        s, e = inner_span(src, el)
        lead, core, trail = split_ws(src[s:e])
        pre = f.get("prefix", "")
        if pre and core.startswith(pre):
            core = core[len(pre):]
        return core, [Edit(s, e, lead + pre + "{{" + path + "}}" + trail)]

    if kind == "text":
        kids = textish(el)
        idx = f.get("idx", 0)
        if len(kids) <= idx:
            raise LookupError("no text node %d in <%s>" % (idx, el.tag))
        s, e, _k = kids[idx]
        lead, core, trail = split_ws(src[s:e])
        return core, [Edit(s, e, lead + "{{" + path + "}}" + trail)]

    if kind == "text_run":
        kids = textish(el)
        limit = el.children[0].start if el.children else None
        run = [k for k in kids if limit is None or k[0] < limit]
        if not run:
            raise LookupError("no text run in <%s>" % el.tag)
        s, e = run[0][0], run[-1][1]
        lead, core, trail = split_ws(src[s:e])
        return core, [Edit(s, e, lead + "{{" + path + "}}" + trail)]

    if kind == "attr":
        span = find_attr_span(src, el, f["attr"])
        if not span:
            return "", []
        _fs, _fe, vs, ve, v = span
        edits = [Edit(vs, ve, "{{" + path + "}}")]
        for m in f.get("mirror", ()):
            mel = resolve_field(item, m) if item is not None else None
            if mel is None:
                continue
            mspan = find_attr_span(src, mel, m["attr"])
            if mspan:
                edits.append(Edit(mspan[2], mspan[3], "{{" + path + "}}"))
        return v, edits

    if kind == "attr_cond":
        span = find_attr_span(src, el, f["attr"])
        if not span:
            return "", []
        fs, fe, _vs, _ve, v = span
        new = ('{{#' + path + '}} ' + f["attr"] + '="{{' + path + '}}"{{/' +
               path + '}}')
        return v, [Edit(fs, fe, new)]

    if kind == "class_cond":
        span = find_attr_span(src, el, "class")
        if not span:
            return "", []
        _fs, _fe, vs, ve, v = span
        extra = " ".join(c for c in v.split() if c != f["base"])
        new = (f["base"] + "{{#" + path + "}} {{" + path + "}}{{/" + path +
               "}}")
        return extra, [Edit(vs, ve, new)]

    if kind == "style_color":
        span = find_attr_span(src, el, "style")
        if not span:
            return "", []
        fs, fe, _vs, _ve, v = span
        m = re.search(r"color\s*:\s*([^;]+)", v)
        if not m:
            return "", []
        color = m.group(1).strip()
        new = ("{{#" + path + "}} style=\"color:{{" + path + "}}\"{{/" + path +
               "}}")
        return color, [Edit(fs, fe, new)]

    if kind == "tag":
        name = el.tag
        return name, [Edit(el.start, el.start + 1 + len(name),
                           "<{{" + path + "}}"),
                      Edit(el.cend, el.end, "</{{" + path + "}}>")]

    if kind == "opt_elem":
        return opt_elem_value(src, el, f)

    raise ValueError("unknown kind: " + kind)


def opt_elem_value(src, el, f):
    """可选元素：整体包进 {{#path}}…{{/path}}，内部文本换成 {{path}}。

    元素若独占一行，行首空白一并挪进区块内部——否则元素缺失时会留下空行。
    """
    path = f["path"]
    outer = src[el.start:el.end]
    rel = el.start
    kids = textish(el)
    inner_val = ""
    if kids:
        s = kids[0][0] - rel
        e = kids[-1][1] - rel
        inner_val = split_ws(src[kids[0][0]:kids[-1][1]])[1]
        outer = outer[:s] + "{{" + path + "}}" + outer[e:]
    if f.get("class_base"):
        span = find_attr_span(src, el, "class")
        if span:
            s = span[2] - rel
            e = span[3] - rel
            cpath = f["class_path"]
            outer = (outer[:s] + f["class_base"] + "{{#" + cpath + "}} {{" +
                     cpath + "}}{{/" + cpath + "}}" + outer[e:])
    lead = ""
    s = el.start
    while s > 0 and src[s - 1] in " \t":
        s -= 1
    if s > 0 and src[s - 1] == "\n":
        s -= 1
        lead = src[s:el.start]
    pre = f.get("prefix", "")
    new = "{{#" + path + "}}" + lead + pre + outer + "{{/" + path + "}}"
    return inner_val, [Edit(s, el.end, new)]


def root_class_split(src, el, base_cls, cls_path, values):
    """把 class 拆成「基础类 + 可选附加类」，附加类名写入 cls_path。"""
    span = find_attr_span(src, el, "class")
    if not span:
        return None
    _fs, _fe, vs, ve, v = span
    extra = " ".join(c for c in v.split() if c != base_cls)
    set_path(values, cls_path, extra)
    new = (base_cls + "{{#" + cls_path + "}} {{" + cls_path + "}}{{/" +
           cls_path + "}}")
    return Edit(vs, ve, new)


def collect_item(src, item, spec):
    """抽取一个条目的所有字段，返回 (值dict, 编辑列表)。"""
    values = {}
    edits = []
    for f in spec["fields"]:
        el = resolve_field(item, f)
        if el is None:
            if f["kind"] == "opt_elem":
                set_path(values, f["path"], "")
                if f.get("class_path"):
                    set_path(values, f["class_path"], "")
                continue
            if f["kind"] == "subloop":
                set_path(values, f["path"], [])
                continue
            raise LookupError("field %s not found in %s"
                              % (f["sel"], spec["path"]))
        if f["kind"] == "subloop":
            val, eds = subloop_value(src, el, f, own_lead=el is not item)
        else:
            val, eds = field_value(src, el, f, item)
        if f.get("strip") and val.startswith(f["strip"]):
            val = val[len(f["strip"]):]
        for t in f.get("trim", ()):
            if val.endswith(t):
                val = val[:-len(t)]
        set_path(values, f["path"], val)
        if f["kind"] == "opt_elem" and f.get("class_path"):
            span = find_attr_span(src, el, "class")
            extra = ""
            if span:
                extra = " ".join(c for c in span[4].split()
                                 if c != f["class_base"])
            set_path(values, f["class_path"], extra)
        edits.extend(eds)
    if spec.get("root_class"):
        base_cls, cls_path = spec["root_class"]
        edit = root_class_split(src, item, base_cls, cls_path, values)
        if edit:
            edits.append(edit)
    return values, edits


def subloop_value(src, container, f, own_lead=True):
    """条目内的嵌套列表：外层 {{#hasX}} 包裹，内层 {{#path}} 迭代。"""
    path = f["path"]
    cap = "has" + path[0].upper() + path[1:]
    items = select(container, f["item_sel"])
    if not items:
        return [], []
    item_spec = {"path": path, "fields": f["fields"]}
    if f.get("root_class"):
        item_spec["root_class"] = f["root_class"]
    body_item = items[f.get("body_index", 0)]
    _vals, body_edits = collect_item(src, body_item, item_spec)
    body_tpl = apply_edits(
        src[body_item.start:body_item.end],
        [Edit(e.start - body_item.start, e.end - body_item.start, e.new)
         for e in body_edits])
    ws = leading_ws(src, body_item.start)
    loop_tpl = "{{#" + path + "}}" + ws + body_tpl + "{{/" + path + "}}"

    head = src[container.start:container.cstart]
    tail = src[container.cend:container.end]
    lead = ""
    s = container.start
    if own_lead:
        while s > 0 and src[s - 1] in " \t":
            s -= 1
        if s > 0 and src[s - 1] == "\n":
            s -= 1
            lead = src[s:container.start]
    else:
        s = container.start
    extra = loop_separator(src, items)
    gap_tail = src[items[-1].end:container.cend]
    if extra:
        avail = len(gap_tail) - len(gap_tail.lstrip("\n"))
        take = min(extra, avail)
        body_tpl += "\n" * take
        gap_tail = gap_tail[take:]
    block = ("{{#" + cap + "}}" + lead + head + loop_tpl +
             gap_tail + tail + "{{/" + cap + "}}")

    rows = []
    for it in items:
        vals, _ = collect_item(src, it, item_spec)
        rows.append(vals)
    return rows, [Edit(s, container.end, block)]


# ----------------------------------------------------------------- 循环

def loop_separator(src, items):
    """条目之间若有空行，循环体末尾需补同样数量的换行。"""
    if len(items) < 2:
        return 0
    gap = src[items[0].end:items[1].start]
    return max(0, gap.count("\n") - 1)


def build_loop(src, spec, root):
    items = select(root, spec["sel"])
    if not items:
        raise LookupError("loop matched nothing: " + spec["sel"])
    body = items[spec.get("body_index", 0)]
    values, edits = collect_item(src, body, spec)
    body_src = src[body.start:body.end]
    rel = [Edit(e.start - body.start, e.end - body.start, e.new) for e in edits]
    body_tpl = apply_edits(body_src, rel)

    ws = leading_ws(src, items[0].start)
    lo = items[0].start - len(ws)
    hi = items[-1].end
    extra = loop_separator(src, items)
    if extra:
        avail = len(src[hi:]) - len(src[hi:].lstrip("\n"))
        take = min(extra, avail)
        body_tpl += "\n" * take
        hi += take
    tpl = ("{{#" + spec["path"] + "}}" + ws + body_tpl +
           "{{/" + spec["path"] + "}}")

    rows = []
    for it in items:
        vals, _ = collect_item(src, it, spec)
        rows.append(vals)
    return tpl, Edit(lo, hi, tpl), rows


# ----------------------------------------------------------------- 字段表

SCALARS = [
    # 导航
    {"sel": ".mob-in", "kind": "inner_raw", "path": "$nav.mob"},
    {"sel": ".nav .brand .bt b", "kind": "inner", "path": "nav.brand"},
    {"sel": ".nav .brand .bt em", "kind": "inner", "path": "nav.brandEn"},
    {"sel": ".nav-in .nav-cta", "kind": "inner", "path": "nav.cta.text"},
    {"sel": ".nav-in .nav-cta", "kind": "attr", "attr": "href",
     "path": "nav.cta.href"},

    # 首屏
    {"sel": "#top .hero-badge b", "kind": "inner", "path": "hero.badgeYear"},
    {"sel": "#top .hero-badge", "kind": "text", "path": "hero.badgeText"},
    {"sel": "#top h1", "kind": "text", "idx": 0, "path": "hero.title"},
    {"sel": "#top h1", "kind": "text", "idx": 1, "path": "hero.titleLine2"},
    {"sel": "#top .en", "kind": "inner", "path": "hero.en"},
    {"sel": "#top .slogan", "kind": "text", "path": "hero.slogan"},
    {"sel": "#top .slogan em", "kind": "inner", "path": "hero.sloganEm"},
    {"sel": "#top .slogan2", "kind": "inner", "path": "hero.slogan2"},
    {"sel": "#top .hero-actions .btn-p", "kind": "text", "path": "hero.ctaJoin"},
    {"sel": "#top .hero-actions .btn-g", "kind": "inner",
     "path": "hero.ctaBrowse"},
    {"sel": "#top .hero-vis .tag", "kind": "inner", "path": "hero.imageTag"},

    # 协会简介
    {"sel": "#about h2.sec", "kind": "inner", "path": "sections.about.title"},
    {"sel": "#about .lead", "kind": "inner", "path": "sections.about.lead"},
    {"sel": "#about .about-quote p:nth-child(1)", "kind": "inner",
     "path": "sections.about.quote0"},
    {"sel": "#about .about-quote p:nth-child(2)", "kind": "inner",
     "path": "sections.about.quote1"},
    {"sel": "#about .about-quote .src", "kind": "inner",
     "path": "sections.about.source"},

    # 协会历程
    {"sel": "#history h2.sec", "kind": "inner", "path": "sections.history.title"},
    {"sel": "#history .lead", "kind": "inner", "path": "sections.history.lead"},

    # 组织架构
    {"sel": "#org h2.sec", "kind": "inner", "path": "sections.org.title"},
    {"sel": "#org .lead", "kind": "inner", "path": "sections.org.lead"},
    {"sel": "#org .org-top .node:nth-child(1) .nm", "kind": "inner",
     "path": "sections.org.topA.name"},
    {"sel": "#org .org-top .node:nth-child(1) .sub", "kind": "inner",
     "path": "sections.org.topA.sub"},
    {"sel": "#org .org-top .node:nth-child(3) .nm", "kind": "inner",
     "path": "sections.org.topB.name"},
    {"sel": "#org .org-top .node:nth-child(3) .sub", "kind": "inner",
     "path": "sections.org.topB.sub"},

    # 活动与项目
    {"sel": "#activity h2.sec", "kind": "inner",
     "path": "sections.activity.title"},
    {"sel": "#activity .lead", "kind": "inner", "path": "sections.activity.lead"},

    # 赛事成绩
    {"sel": "#results h2.sec", "kind": "inner", "path": "sections.results.title"},
    {"sel": "#results .lead", "kind": "inner", "path": "sections.results.lead"},
    {"sel": "#results .note", "kind": "inner", "path": "sections.results.note"},
    {"sel": "#results .kpis", "kind": "inner_raw", "path": "$results.kpis"},
    {"sel": "#results table caption", "kind": "inner",
     "path": "sections.results.caption"},
    {"sel": "#results noscript", "kind": "outer_raw", "path": "$results.noscript"},
    {"sel": "#results tfoot", "kind": "inner_raw", "path": "$results.tfoot"},

    # 成员风采
    {"sel": "#member h2.sec", "kind": "inner", "path": "sections.member.title"},
    {"sel": "#member .lead", "kind": "inner", "path": "sections.member.lead"},

    # 新闻动态
    {"sel": "#news h2.sec", "kind": "inner", "path": "sections.news.title"},
    {"sel": "#news .lead", "kind": "inner", "path": "sections.news.lead"},
    {"sel": "#news .notice h3", "kind": "inner",
     "path": "sections.news.noticeTitle"},

    # 加入我们
    {"sel": "#join h2.sec", "kind": "inner", "path": "sections.join.title"},
    {"sel": "#join .lead", "kind": "inner", "path": "sections.join.lead"},
    {"sel": "#join .card h3", "kind": "inner", "path": "sections.join.rightsTitle"},

    # 联系方式
    {"sel": "#contact h2.sec", "kind": "inner", "path": "sections.contact.title"},
    {"sel": "#contact .lead", "kind": "inner", "path": "sections.contact.lead"},

    # 页脚
    {"sel": "footer .fl .bt b", "kind": "inner", "path": "footer.brand"},
    {"sel": "footer .fl .bt em", "kind": "inner", "path": "footer.brandEn"},
    {"sel": "footer .foot > div:nth-child(1) > p:nth-of-type(1)", "kind": "inner",
     "path": "footer.slogan"},
    {"sel": "footer .foot > div:nth-child(1) > p:nth-of-type(2)", "kind": "text",
     "idx": 0, "path": "footer.line1"},
    {"sel": "footer .foot > div:nth-child(1) > p:nth-of-type(2)", "kind": "text",
     "idx": 1, "path": "footer.line2"},
    {"sel": "footer .copy span:nth-child(1)", "kind": "inner",
     "path": "footer.copyright"},
    {"sel": "footer .copy span:nth-child(2)", "kind": "inner",
     "path": "footer.source"},
]

LOOPS = [
    {"path": "nav.links", "sel": ".nav-links > a", "body_index": 0,
     "fields": [
         {"sel": "$self", "kind": "inner", "path": "text"},
         {"sel": "$self", "kind": "attr", "attr": "href", "path": "href"},
     ]},
    {"path": "hero.stats", "sel": "#top .hero-stats > div", "body_index": 2,
     "fields": [
         {"sel": "b", "kind": "attr", "attr": "data-c", "path": "value"},
         {"sel": "b", "kind": "attr_cond", "attr": "data-suffix",
          "path": "suffix"},
         {"sel": "b", "kind": "inner", "path": "display"},
         {"sel": "span", "kind": "inner", "path": "label"},
     ]},
    {"path": "sections.about.pillars", "sel": "#about .pillars .pillar",
     "body_index": 0, "fields": [
         {"sel": ".no", "kind": "inner", "path": "no"},
         {"sel": "b", "kind": "inner", "path": "title"},
         {"sel": "span", "kind": "inner", "path": "desc"},
     ]},
    {"path": "sections.about.tags", "sel": "#about .tags .tag-s",
     "body_index": 0, "fields": [
         {"sel": "$self", "kind": "inner", "path": "text"},
         {"sel": "$self", "kind": "class_cond", "base": "tag-s", "path": "on"},
     ]},
    {"path": "sections.history.columns", "sel": "#history .grid.g2 > .tl",
     "body_index": 0, "fields": [
         {"sel": "$self", "kind": "subloop", "path": "items",
          "item_sel": "> .tl-i", "body_index": 1,
          "root_class": ("tl-i", "extra"), "fields": [
              {"sel": ".tl-y", "kind": "inner", "path": "year"},
              {"sel": ".tl-t", "kind": "inner", "path": "title"},
              {"sel": ".tl-d", "kind": "inner", "path": "desc"},
              {"sel": ".tl-badge", "kind": "opt_elem", "path": "badge",
               "class_base": "tl-badge", "class_path": "badgeClass"},
          ]},
     ]},
    {"path": "sections.org.depts", "sel": "#org .depts .dept",
     "body_index": 0, "fields": [
         {"sel": ".dn", "kind": "inner", "path": "name"},
         {"sel": ".dd", "kind": "inner", "path": "desc"},
         {"sel": ".dc", "kind": "inner", "path": "meta"},
     ]},
    {"path": "sections.org.cards", "sel": "#org .card .grid.g3 > div",
     "body_index": 0, "fields": [
         {"sel": ".c-lab", "kind": "inner", "path": "lab"},
         {"sel": ".c-val", "kind": "text_run", "path": "val",
          "trim": ["&ensp;"]},
         {"sel": ".c-val span", "kind": "opt_elem", "path": "role",
          "prefix": "&ensp;"},
         {"sel": ".c-sub", "kind": "inner", "path": "sub"},
     ]},
    {"path": "sections.activity.items", "sel": "#activity .act",
     "body_index": 0, "fields": [
         {"sel": "$self", "kind": "attr", "attr": "data-img", "path": "img",
          "mirror": [{"sel": ".act-img img", "attr": "src"}]},
         {"sel": "$self", "kind": "attr", "attr": "data-cap", "path": "cap"},
         {"sel": ".act-img img", "kind": "attr", "attr": "alt", "path": "imgAlt"},
         {"sel": ".act-img img", "kind": "attr", "attr": "width",
          "path": "imgW"},
         {"sel": ".act-img img", "kind": "attr", "attr": "height",
          "path": "imgH"},
         {"sel": ".act-img .flag", "kind": "inner", "path": "flag"},
         {"sel": ".act-bd h3", "kind": "inner", "path": "title"},
         {"sel": ".act-meta span:nth-child(1)", "kind": "text", "path": "time"},
         {"sel": ".act-meta span:nth-child(2)", "kind": "text", "path": "place"},
         {"sel": ".act-bd p", "kind": "inner", "path": "desc"},
         {"sel": ".act-kpi", "kind": "subloop", "path": "kpis",
          "item_sel": "> div", "fields": [
              {"sel": "b", "kind": "inner", "path": "value"},
              {"sel": "span", "kind": "inner", "path": "label"},
          ]},
     ]},
    {"path": "sections.results.summary", "sel": "#results .grid.g4 .card",
     "body_index": 0, "fields": [
         {"sel": ".c-lab", "kind": "style_color", "path": "color"},
         {"sel": ".c-lab", "kind": "inner", "path": "lab"},
         {"sel": "div:nth-of-type(2)", "kind": "inner", "path": "title"},
         {"sel": "p", "kind": "inner", "path": "desc"},
     ]},
    {"path": "sections.member.kpis", "sel": "#member .kpis > div",
     "body_index": 0, "fields": [
         {"sel": "b", "kind": "attr", "attr": "data-c", "path": "value"},
         {"sel": "b", "kind": "inner", "path": "display"},
         {"sel": "span", "kind": "inner", "path": "label"},
     ]},
    {"path": "sections.member.figures", "sel": "#member .memb figure",
     "body_index": 0, "fields": [
         {"sel": "$self", "kind": "attr", "attr": "data-img", "path": "img",
          "mirror": [{"sel": "img", "attr": "src"}]},
         {"sel": "$self", "kind": "attr", "attr": "data-cap", "path": "cap"},
         {"sel": "img", "kind": "attr", "attr": "alt", "path": "imgAlt"},
         {"sel": "img", "kind": "attr", "attr": "width", "path": "imgW"},
         {"sel": "img", "kind": "attr", "attr": "height", "path": "imgH"},
         {"sel": "figcaption b", "kind": "inner", "path": "title"},
         {"sel": "figcaption span", "kind": "inner", "path": "sub"},
     ]},
    {"path": "sections.news.items", "sel": "#news .news-list .n-item",
     "body_index": 0, "fields": [
         {"sel": ".n-date", "kind": "text", "idx": 0, "path": "date"},
         {"sel": ".n-date span", "kind": "inner", "path": "tag"},
         {"sel": ".n-bd h3", "kind": "inner", "path": "title"},
         {"sel": ".n-bd p", "kind": "inner", "path": "desc"},
         {"sel": ".n-kind", "kind": "inner", "path": "kind"},
         {"sel": ".n-kind", "kind": "class_cond", "base": "n-kind",
          "path": "kindClass"},
     ]},
    {"path": "sections.news.notices", "sel": "#news .notice ul > li",
     "body_index": 0, "fields": [
         {"sel": "b", "kind": "inner", "path": "no"},
         {"sel": "div", "kind": "text", "idx": 0, "path": "title"},
         {"sel": "div div i", "kind": "inner", "path": "sub"},
     ]},
    {"path": "sections.join.steps", "sel": "#join .steps .step",
     "body_index": 0, "fields": [
         {"sel": ".sn", "kind": "inner", "path": "no"},
         {"sel": "b", "kind": "inner", "path": "title"},
         {"sel": "span", "kind": "inner", "path": "desc"},
     ]},
    {"path": "sections.join.rights", "sel": "#join .card ul.grid > li",
     "body_index": 0, "fields": [
         {"sel": "$self", "kind": "inner", "path": "text", "prefix": "· "},
     ]},
    {"path": "sections.contact.cards", "sel": "#contact .contact > *",
     "body_index": 0, "fields": [
         {"sel": "$self", "kind": "tag", "path": "tag"},
         {"sel": "$self", "kind": "attr_cond", "attr": "href", "path": "href"},
         {"sel": ".c-lab", "kind": "inner", "path": "lab"},
         {"sel": ".c-val", "kind": "inner", "path": "val"},
         {"sel": ".c-sub", "kind": "inner", "path": "sub"},
     ]},
    {"path": "sections.contact.info", "sel": "#contact .card .grid.g3 > div",
     "body_index": 0, "fields": [
         {"sel": ".c-lab", "kind": "inner", "path": "lab"},
         {"sel": ".c-val", "kind": "attr_cond", "attr": "style",
          "path": "style"},
         {"sel": ".c-val", "kind": "inner", "path": "val"},
         {"sel": ".c-sub", "kind": "inner", "path": "sub"},
     ]},
    {"path": "footer.nav.links", "sel": "footer .foot > div:nth-child(2) > a",
     "body_index": 0, "fields": [
         {"sel": "$self", "kind": "inner", "path": "text"},
         {"sel": "$self", "kind": "attr", "attr": "href", "path": "href"},
     ]},
    {"path": "footer.join.links", "sel": "footer .foot > div:nth-child(3) > a",
     "body_index": 0, "fields": [
         {"sel": "$self", "kind": "inner", "path": "text"},
         {"sel": "$self", "kind": "attr", "attr": "href", "path": "href"},
     ]},
]


# ----------------------------------------------------------------- 主流程

def parse_results_js(src):
    m = re.search(r"var RESULTS=\[([\s\S]*?)\];", src)
    if not m:
        raise LookupError("RESULTS array not found")
    rows = []
    for rm in re.finditer(
            r"\[\s*\"([^\"]*)\"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,"
            r"\s*(\d+)\s*,\s*([\d.]+)\s*\]", m.group(1)):
        rows.append({
            "name": rm.group(1),
            "signupGroups": int(rm.group(2)),
            "signupPeople": int(rm.group(3)),
            "awardGroups": int(rm.group(4)),
            "awardPeople": int(rm.group(5)),
        })
    if len(rows) != 20:
        raise ValueError("expected 20 result rows, got %d" % len(rows))
    return rows


def apply_derived_refs(data):
    """把正文里重复出现的合计数改成派生占位符。

    构建时 {count}、{signupPeople}、{rateByGroup} 等会按赛事明细重算，
    改明细不用再手动同步页面上的数字。
    """
    s = data["sections"]

    def swap(container, key, old, new):
        if old not in container[key]:
            raise LookupError("derived ref not found: %s / %s" % (key, old))
        container[key] = container[key].replace(old, new)

    swap(s["history"], "lead", "扩展至 20 项", "扩展至 {count} 项")
    swap(s["results"], "caption", "共 20 项赛事", "共 {count} 项赛事")
    swap(s["member"], "lead", "共 109 人", "共 {memberCount} 人")
    swap(s["member"]["kpis"][3], "label", "70.6%", "{memberRatio}%")

    data["hero"]["stats"][1]["value"] = "{count}"
    data["hero"]["stats"][1]["display"] = "{count}"

    first = s["activity"]["items"][0]
    swap(first, "desc", "发展为 20 项赛事", "发展为 {count} 项赛事")
    first["kpis"][0]["value"] = "{count}"
    first["kpis"][1]["value"] = "{signupPeople}"
    first["kpis"][2]["value"] = "{rateByGroup}%"

    s["results"]["summary"][2]["desc"] = s["results"]["summary"][2]["desc"].replace(
        "82 组 282 人次，占全届获奖人次的 21.2%",
        "{topAwardGroups} 组 {topAwardPeople} 人次，占全届获奖人次的 {topAwardRatio}%")


def build():
    src = open(SRC, encoding="utf-8").read()
    parser = Parser(src)
    parser.feed(src)
    parser.close()

    data = {}
    edits = []

    # ---- 整块由 build.py 生成 ----
    m = re.search(r"<title>[\s\S]*?</script>", src)
    edits.append(Edit(m.start(), m.end(), "{{$head}}"))

    m = re.search(r"var RESULTS=\[[\s\S]*?\];", src)
    edits.append(Edit(m.start(), m.end(), "{{$results.js}}"))

    # ---- 标量字段 ----
    for f in SCALARS:
        kind = f["kind"]
        el = one(parser.root, f["sel"])
        if kind == "inner_raw":
            edits.append(Edit(el.cstart, el.cend, "{{" + f["path"] + "}}"))
            continue
        if kind == "outer_raw":
            edits.append(Edit(el.start, el.end, "{{" + f["path"] + "}}"))
            continue
        val, eds = field_value(src, el, f)
        set_path(data, f["path"], val)
        edits.extend(eds)

    # ---- 循环 ----
    for spec in LOOPS:
        _tpl, edit, rows = build_loop(src, spec, parser.root)
        set_path(data, spec["path"], rows)
        edits.append(edit)

    # ---- 赛事明细（数据在 JS 数组里） ----
    set_path(data, "sections.results.rows", parse_results_js(src))
    apply_derived_refs(data)

    template = apply_edits(src, edits)

    # ---- 站点级元信息 ----
    data["site"] = {
        "url": "https://tchao8820.github.io/ctbu-kexie-website/",
        "ogImage": "https://tchao8820.github.io/ctbu-kexie-website/og-image.png",
        "logo": "assets/img/logo.png",
    }
    data["meta"] = {
        "title": "重庆工商大学科技协会 CTBU-STA | 科技点燃梦想，创新赋能未来",
        "description": "重庆工商大学科技协会（CTBU-STA）官方宣传站：协会简介、历程与组织架构、活动与项目、科创月赛事成绩、成员风采、新闻动态与加入入口。指导单位机械工程学院，学术科技类学生社团，2002 年经共青团重庆工商大学委员会批准注册成立。",
        "keywords": "重庆工商大学科技协会,CTBU-STA,学生科技创新文化活动月,科创月,机械工程学院,学生社团,3D打印,机器人,先进成图",
        "author": "重庆工商大学科技协会 CTBU-STA",
        "themeColor": "#0A1628",
        "ogTitle": "重庆工商大学科技协会 CTBU-STA",
        "ogDescription": "科技点燃梦想，创新赋能未来。",
        "siteName": "重庆工商大学科技协会 CTBU-STA",
        "ogImageAlt": "重庆工商大学科技协会 CTBU-STA 会标与宣传标语",
        "orgDescription": "重庆工商大学科技协会（CTBU-STA）是学术科技类学生社团，指导单位为机械工程学院，宗旨是普及科学知识、培养创新思维、提升实践能力。",
        "orgAddress": "重庆工商大学机械工程学院",
        "telephone": "+86-198-2251-6790",
        "alternateNames": ["CTBU-STA", "重庆工商大学学生科技协会"],
        "parentOrg": "重庆工商大学",
    }

    tpl_path = os.path.join(ROOT, "tools", "template.html")
    with open(tpl_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(template)
    json_path = os.path.join(ROOT, "content", "site.json")
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("template.html: %d bytes" % os.path.getsize(tpl_path))
    print("site.json    : %d bytes" % os.path.getsize(json_path))


if __name__ == "__main__":
    build()
