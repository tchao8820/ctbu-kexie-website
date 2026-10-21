#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTBU-STA 官网 · 一键切换站点域名
=================================
绑定自定义域名（或从 github.io 换回）后，跑这一条命令即可把全部
「域名相关」的位置一次性改干净：

  · content/site.json → site.url / site.ogImage（以及任何内含旧域名的字段）
  · index.html        → 由 content/site.json + tools/template.html 重新构建
                      → <link rel="canonical">
                      → og:url / og:image / twitter:image
                      → JSON-LD 里的 @id / url / logo
  · sitemap.xml       → <loc> 全部条目
  · robots.txt        → Sitemap: 行

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
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "content", "site.json")


def norm(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u.rstrip("/")


def replace_in(node, old: str, new: str, hits):
    """把 JSON 树里所有出现旧域名的字符串换掉。"""
    if isinstance(node, str):
        if old and old in node:
            hits.append(node)
            return node.replace(old, new)
        return node
    if isinstance(node, list):
        return [replace_in(v, old, new, hits) for v in node]
    if isinstance(node, dict):
        return {k: replace_in(v, old, new, hits) for k, v in node.items()}
    return node


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
    data_path = os.path.join(root, "content", "site.json")

    if not os.path.isfile(data_path):
        print(f"[错误] 找不到 {data_path}", file=sys.stderr)
        return 2

    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    old_base = norm(data.get("site", {}).get("url", ""))
    if not old_base:
        print("[错误] content/site.json 的 site.url 为空，无法确定当前域名", file=sys.stderr)
        return 3

    hits = []
    new_data = replace_in(data, old_base, new_base, hits)

    if old_base == new_base:
        print(f"[提示] 当前域名已是 {new_base}，无需修改。")
    else:
        print(f"域名切换：{old_base}")
        print(f"       →  {new_base}")
        print(f"content/site.json 中命中 {len(hits)} 处：")
        for h in hits:
            print(f"   · {h[:150]}")

    if args.dry_run:
        print("\n[--dry-run] 未写入任何文件。")
        return 0

    if old_base != new_base:
        with open(data_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(new_data, ensure_ascii=False, indent=2) + "\n")
        print(f"已更新 {data_path}")

    # ---- 重建 index.html ----
    build = os.path.join(root, "tools", "build.py")
    if os.path.isfile(build):
        r = subprocess.run([sys.executable, build], capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0:
            print("[错误] index.html 重建失败，已中止。", file=sys.stderr)
            return 4
    else:
        print(f"[警告] 未找到 {build}，index.html 未重建！")

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
