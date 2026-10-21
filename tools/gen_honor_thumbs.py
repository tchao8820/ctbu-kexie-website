#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把协会荣誉档案里的证书照片处理成网页可用的统一缩略图。

素材（协会历年荣誉档案）不在仓库里，所以本脚本要求显式传入源目录：

    python tools/gen_honor_thumbs.py --src "E:/00 科技协会荣誉档案/01_协会集体荣誉"

处理口径
--------
* 统一裁成 4:3（cover：先等比放大到覆盖目标框，再按 --pos 指定的焦点裁切），
  这样证书墙的每张图尺寸一致，排版不会参差。
* 必须先做 EXIF 方向矫正：档案里不少手机拍摄的证书是横向存储、靠 EXIF 标记
  竖排的，不矫正会出现整张证书侧倒。
* 输出 JPEG q86，宽度 480，配合页面的 loading="lazy" 使用。

清单写死在 MANIFEST 里而不是自动扫描：档案目录名带中文与括号、层级也会变，
自动扫描会静默匹配到错误文件；写死则路径一变就明确报缺失。
"""
import argparse
import json
import os
import sys
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets", "img", "honors")
TW, TH = 480, 360

# (源文件相对路径, 输出文件名, 焦点 x, 焦点 y, 说明)
MANIFEST = [
    ("02_星级社团（四星·五星）/24-25五星级社团.jpg",   "xingji-2425.jpg",  .5, .5, "2024—2025 学年 五星级社团"),
    ("02_星级社团（四星·五星）/23-24五星级社团.jpg",   "xingji-2324.jpg",  .5, .5, "2023—2024 学年 五星级社团"),
    ("02_星级社团（四星·五星）/22-23四星级社团.jpg",   "xingji-2223.jpg",  .5, .5, "2022—2023 学年 四星级社团"),
    ("04_五四红旗团支部·先进团支部/24-25“五四”红旗团支部.jpg", "wusi-2425.jpg", .5, .5, "2024—2025 学年 五四红旗团支部"),
    ("04_五四红旗团支部·先进团支部/23-24先进团支部.png", "zhibu-2324.jpg", .5, .5, "2023—2024 学年 先进团支部"),
    ("04_五四红旗团支部·先进团支部/22-23先进团支部.png", "zhibu-2223.jpg", .5, .5, "2022—2023 学年 先进团支部"),
    ("03_活力社团（全国·市级）/23-24活力社团.jpg",      "huoli-2324.jpg",  .5, .5, "2023—2024 学年 全国高校活力社团"),
    ("01_优秀学生社团/23-24优秀学生社团.jpg",          "youxiu-2324.jpg", .5, .5, "2023—2024 学年 优秀学生社团"),
    ("01_优秀学生社团/22-23优秀学生社团.png",          "youxiu-2223.jpg", .5, .5, "2022—2023 学年 优秀学生社团"),
]


def cover(im, tw, th, pos):
    w, h = im.size
    s = max(tw / w, th / h)
    im2 = im.resize((int(round(w * s)), int(round(h * s))), Image.LANCZOS)
    x = int(round((im2.width - tw) * pos[0]))
    y = int(round((im2.height - th) * pos[1]))
    return im2.crop((x, y, x + tw, y + th))


def main():
    ap = argparse.ArgumentParser(description="生成荣誉证书缩略图")
    ap.add_argument("--src", required=True, help="证书源目录（协会荣誉档案/01_协会集体荣誉）")
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    src = os.path.abspath(args.src)
    if not os.path.isdir(src):
        print(f"[错误] 源目录不存在：{src}", file=sys.stderr)
        return 2
    os.makedirs(args.out, exist_ok=True)

    made, missing = [], []
    for rel, name, px, py, desc in MANIFEST:
        f = os.path.join(src, rel.replace("/", os.sep))
        if not os.path.isfile(f):
            missing.append(rel)
            continue
        if args.dry_run:
            made.append((name, "（dry-run）"))
            continue
        im = Image.open(f)
        im = ImageOps.exif_transpose(im).convert("RGB")
        small = im.width < TW
        out = cover(im, TW, TH, (px, py))
        dst = os.path.join(args.out, name)
        out.save(dst, "JPEG", quality=86, optimize=True, progressive=True)
        made.append((name, f"{os.path.getsize(dst)/1024:.0f} KB"
                     + ("（源图偏小，已拉伸）" if small else "")))

    print(f"源目录：{src}")
    print(f"输出目录：{args.out}")
    for name, info in made:
        print(f"   ✓ {name:<20} {info}")
    if missing:
        print(f"\n[警告] 清单中有 {len(missing)} 个源文件缺失（归档改名或移动了）：")
        for rel in missing:
            print("   ×", rel)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())