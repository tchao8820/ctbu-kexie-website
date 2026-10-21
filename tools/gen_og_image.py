#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成社交分享卡片 og-image.png（1200×630），与新站点的「学术年报」视觉一致。

    python tools/gen_og_image.py            # 覆盖仓库根目录的 og-image.png
    python tools/gen_og_image.py --dry-run  # 只打印将要写入的尺寸，不落盘

设计口径与 tools/template.html 的 CSS 令牌保持一致：
    纸 #FBF9F4 / 墨 #14243A / 深青 #0E6E6E / 细线 #E4DFD2
若改动站点配色，请同步这里的常量与 template.html 的 :root。

字体依赖：优先使用系统已装的思源宋体（Noto Serif SC）；找不到时退回其他
衬线中文字体。两个都找不到会明确报错并给出安装提示。
"""
import argparse
import json
import os
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "og-image.png")
LOGO = os.path.join(ROOT, "assets", "img", "logo.png")
DATA = os.path.join(ROOT, "content", "site.json")

W, H = 1200, 630
M = 72                                    # 页边距

PAPER = (251, 249, 244)
INK = (20, 36, 58)
INK2 = (58, 71, 89)
MUTED = (110, 118, 134)
RULE = (228, 223, 210)
TEAL = (14, 110, 110)
TEAL_T = (227, 239, 236)

# 衬线（标题/正文）：思源宋体 > 宋体 > 楷体
SERIF_CANDIDATES = [
    r"C:\Windows\Fonts\NotoSerifSC-VF.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\simkai.ttf",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
]
# 无衬线（UI/小字）
SANS_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\Deng.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]
# 等宽（数字/英文标签）
MONO_CANDIDATES = [
    r"C:\Windows\Fonts\consola.ttf",
    r"C:\Windows\Fonts\lucon.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]


def pick(cands, what):
    for p in cands:
        if os.path.isfile(p):
            return p
    print(f"[错误] 找不到可用的{what}字体，以下路径都不存在：", file=sys.stderr)
    for p in cands:
        print("   ·", p, file=sys.stderr)
    print("请安装思源宋体（Noto Serif SC）后重试。", file=sys.stderr)
    sys.exit(2)


def font(path, size, wght=None):
    f = ImageFont.truetype(path, size)
    # 变量字体：尝试取到指定字重，失败就用默认实例
    if wght is not None:
        try:
            f.set_variation_by_axes([wght])
        except Exception:
            pass
    return f


def spaced(draw, xy, text, f, fill, gap=0, anchor_left=True):
    """逐字绘制以支持字距（PIL 没有 letter-spacing）。返回结束的 x。"""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + gap
    return x - gap


def spaced_w(draw, text, f, gap):
    if not text:
        return 0
    return sum(draw.textlength(c, font=f) for c in text) + gap * (len(text) - 1)


def main():
    ap = argparse.ArgumentParser(description="生成 og-image.png")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    with open(DATA, encoding="utf-8") as fh:
        data = json.load(fh)
    url = data["site"]["url"]
    host = url.split("://", 1)[-1].rstrip("/")
    rows = data["sections"]["results"]["rows"]
    member = data["sections"]["member"]["kpis"]
    n_events = len(rows)
    n_signup = sum(r["signupPeople"] for r in rows)
    n_award = sum(r["awardPeople"] for r in rows)
    rate = n_award * 100.0 / n_signup

    serif_p = pick(SERIF_CANDIDATES, "衬线")
    sans_p = pick(SANS_CANDIDATES, "无衬线")
    mono_p = pick(MONO_CANDIDATES, "等宽")

    F_BRAND = font(serif_p, 27, 700)
    F_EN = font(mono_p, 12)
    F_META = font(mono_p, 13)
    F_TITLE = font(serif_p, 62, 700)
    F_SLOGAN = font(sans_p, 21)
    F_NUM = font(mono_p, 36)
    F_LAB = font(sans_p, 13)
    F_URL = font(mono_p, 13)

    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)

    # 品牌锁定：会标 + 中文名 + 英文缩写
    if os.path.isfile(LOGO):
        lg = Image.open(LOGO).convert("RGBA")
        s = 56
        lg = lg.resize((s, s), Image.LANCZOS)
        im.paste(lg, (M, M - 6), lg)
        bx = M + s + 16
    else:
        bx = M
    d.text((bx, M + 1), data["nav"]["brand"], font=F_BRAND, fill=INK)
    spaced(d, (bx, M + 38), data["nav"]["brandEn"], F_EN, MUTED, gap=2.2)
    spaced(d, (W - M - spaced_w(d, "2002 — 2026", F_META, 2.6), M + 20),
           "2002 — 2026", F_META, MUTED, gap=2.6)

    y_rule = 168
    d.line([(M, y_rule), (W - M, y_rule)], fill=INK, width=2)

    # 主标题：两行宋体大字，「创新」用深青
    y = y_rule + 58
    d.text((M, y), "科技点燃梦想", font=F_TITLE, fill=INK)
    d.text((M, y + 78), "创新", font=F_TITLE, fill=TEAL)
    d.text((M + d.textlength("创新", font=F_TITLE), y + 78), "赋能未来", font=F_TITLE, fill=INK)

    # 一句话定位：按卡片宽度截断。宁可退到最近的顿号/逗号，也不要切在词中间
    desc = data["meta"]["description"]
    limit = W - 2 * M
    if d.textlength(desc, font=F_SLOGAN) > limit:
        cut = len(desc)
        while cut and d.textlength(desc[:cut] + "…", font=F_SLOGAN) > limit:
            cut -= 1
        head = desc[:cut]
        for sep in ("、", "，", "。", "；"):
            i = head.rfind(sep)
            if i >= 8:
                head = head[:i]
                break
        desc = head.rstrip("、，。； ") + "…"
    d.text((M, y + 78 + 96), desc, font=F_SLOGAN, fill=MUTED)

    # 数据行：与站点 hero-stats / .kpis 同一套（2px 墨线 + 细线分隔）
    y_s = H - M - 108
    d.line([(M, y_s), (W - M, y_s)], fill=INK, width=2)
    stats = [
        (str(n_events), "项赛事"),
        (f"{n_signup}", "报名人次"),
        (f"{rate:.1f}%", "获奖率（按人次）"),
        (member[0]["display"], "会员人数"),
    ]
    cw = (W - 2 * M) / len(stats)
    for i, (val, lab) in enumerate(stats):
        cx = M + i * cw
        if i:
            d.line([(cx, y_s + 18), (cx, y_s + 74)], fill=RULE, width=1)
        px = cx + (18 if i else 0)
        d.text((px, y_s + 20), val, font=F_NUM, fill=INK)
        d.text((px, y_s + 68), lab, font=F_LAB, fill=MUTED)

    d.line([(M, H - M + 6), (W - M, H - M + 6)], fill=RULE, width=1)
    # 这行含中文，必须用有 CJK 字形的字体——等宽字体没有汉字，会渲染成方框
    d.text((M, H - M + 16),
           f"{data['nav']['brand']} · {data['nav']['brandEn']}", font=F_LAB, fill=MUTED)
    d.text((W - M - d.textlength(host, font=F_URL), H - M + 18), host,
           font=F_URL, fill=MUTED)

    if args.dry_run:
        print(f"[--dry-run] 将写出 {OUT}（{W}×{H}）")
        return 0

    im.save(OUT, "PNG", optimize=True)
    print(f"已写出 {OUT}（{W}×{H}，{os.path.getsize(OUT)} 字节）")
    return 0


if __name__ == "__main__":
    sys.exit(main())