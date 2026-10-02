#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTBU-STA 官网 · 一键切换站点域名
=================================
绑定自定义域名（或从 github.io 换回）后，跑这一条命令即可把全部
「域名相关」的位置一次性改干净：

  · index.html  → <link rel="canonical">
                → og:url / og:image / twitter:image
                → JSON-LD 里的 @id / url / logo
  · sitemap.xml → <loc> 全部条目
  · robots.txt  → Sitemap: 行

顺带可选地生成 CNAME 文件（--write-cname）。

用法
----
  # 只改文件（推荐先带 --dry-run 看一眼）
  python tools/set_site_url.py --site-url https://kexie.ctbu.edu.cn --dry-run
  python tools/set_site_url.py --site-url https://kexie.ctbu.edu.cn

  # 域名解析确认无误后，一并落 CNAME 文件
  python tools/set_site_url.py --site-url https://kexie.ctbu.edu.cn --write-cname

  # 还原成 github.io 默认地址（会同时删掉 CNAME 文件）
  python tools/set_site_url.py --site-url https://tchao8820.github.io/ctbu-kexie-website --remove-cname

注意
----
* 换域名是「破坏性」改动：一旦 CNAME 文件存在，github.io 地址就会 301 跳转，
  所以务必等新域名的 DNS 解析生效后再执行本脚本。
* 执行完记得 git commit && git push。
"""

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON_RE = re.compile(r'<link rel="canonical" href="([^"]+)"')
OGURL_RE = re.compile(r'<meta property="og:url" content="([^"]+)"')


def norm(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u.rstrip("/")


def current_base(html: str) -> str:
    for rx in (CANON_RE, OGURL_RE):
        m = rx.search(html)
        if m:
            return m.group(1).rstrip("/")
    return ""


def main():
    ap = argparse.ArgumentParser(description="切换官网站点域名")
    ap.add_argument("--root", default=ROOT, help="站点发布根目录（默认脚本上一级）")
    ap.add_argument("--site-url", required=True, help="新的站点根地址")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    ap.add_argument("--write-cname", action="store_true", help="同时写出 CNAME 文件")
    ap.add_argument("--remove-cname", action="store_true", help="删除 CNAME 文件（回到 github.io）")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    new_base = norm(args.site_url)
    idx_path = os.path.join(root, "index.html")

    if not os.path.isfile(idx_path):
        print(f"[错误] 找不到 {idx_path}", file=sys.stderr)
        return 2

    html = open(idx_path, encoding="utf-8").read()
    old_base = current_base(html)
    if not old_base:
        print("[错误] index.html 中未找到 canonical / og:url，无法确定当前域名", file=sys.stderr)
        return 3

    if old_base == new_base:
        print(f"[提示] 当前域名已是 {new_base}，无需修改。")
    else:
        n = html.count(old_base)
        print(f"域名切换：{old_base}")
        print(f"       →  {new_base}")
        print(f"index.html 中命中 {n} 处（canonical / og:url / og:image / twitter:image / JSON-LD）")

    if args.dry_run:
        # 只统计将要改动的行，不落盘
        for i, line in enumerate(html.splitlines(), 1):
            if old_base and old_base in line:
                print(f"   L{i}: {line.strip()[:150]}")
        print("\n[--dry-run] 未写入任何文件。")
        return 0

    if old_base != new_base:
        html = html.replace(old_base, new_base)
        open(idx_path, "w", encoding="utf-8", newline="\n").write(html)
        print(f"已更新 {idx_path}")

    # ---- 重新生成 sitemap.xml / robots.txt ----
    gen = os.path.join(root, "tools", "gen_seo.py")
    if os.path.isfile(gen):
        r = subprocess.run(
            [sys.executable, gen, "--root", root, "--site-url", new_base],
            capture_output=True, text=True,
        )
        print(r.stdout.strip() or r.stderr.strip())
    else:
        print(f"[警告] 未找到 {gen}，sitemap.xml / robots.txt 未同步！")

    # ---- CNAME ----
    cname = os.path.join(root, "CNAME")
    if args.remove_cname:
        if os.path.isfile(cname):
            os.remove(cname)
            print("已删除 CNAME 文件，站点回到 github.io 默认地址")
    elif args.write_cname:
        host = new_base.split("://", 1)[-1].split("/", 1)[0]
        with open(cname, "w", encoding="ascii", newline="\n") as f:
            f.write(host + "\n")
        print(f"已写出 CNAME → {host}")
    else:
        print("（未改动 CNAME 文件；确认解析生效后加 --write-cname 生成）")

    print("\n完成。下一步：git add -A && git commit -m \"chore: 切换站点域名\" && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
