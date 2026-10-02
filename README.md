# 重庆工商大学科技协会官网（CTBU-STA）

> 科技点燃梦想，创新赋能未来

本仓库是重庆工商大学科技协会官网的发布源码，用于 **GitHub Pages** 静态托管。

线上地址：<https://tchao8820.github.io/ctbu-kexie-website/>

## 仓库内容

```
index.html        官网全部内容（单文件，含内联样式、脚本与 base64 图片）
404.html          自定义 404 错误页（GitHub Pages 自动启用，已被 robots 屏蔽）
sitemap.xml       站点地图（自动生成，勿手工编辑）
robots.txt        爬虫规则 + sitemap 声明（自动生成，勿手工编辑）
og-image.png      社交分享卡片 1200×630（微信 / QQ / Twitter 预览用）
CNAME.example     CNAME 文件模板，绑定自定义域名时参考（当前未启用）
.nojekyll         阻止 GitHub Pages 走 Jekyll 构建，保证原样发布
tools/gen_seo.py        扫描发布目录，自动生成 sitemap.xml 与 robots.txt
tools/set_site_url.py   换域名时一键同步全部域名相关位置
README.md         本说明
```

官网为**单文件静态站点**：零外部请求、零接口调用、零构建步骤、无需任何环境变量，
因此发布方式就是「把文件放好」，没有构建过程。

## 如何更新内容

1. 修改源模板 `F:\科技协会官网\template.html`
2. 在 `F:\科技协会官网\` 下重建：`python F:\.workbuddy\scan\build_site.py`
3. 把新的 `index.html` 覆盖到本仓库根目录
4. 重新生成 SEO 文件：`python tools/gen_seo.py`
5. 提交并推送，GitHub Pages 会在 1–2 分钟内自动更新

> 站点上线后 `lastmod` 想刷新，只需重跑 `tools/gen_seo.py`。

## 搜索引擎优化

| 文件 | 作用 | 生成方式 |
|---|---|---|
| `sitemap.xml` | 向搜索引擎提交全部公开页面 | `python tools/gen_seo.py` |
| `robots.txt` | 允许全站抓取 + 声明 sitemap + 屏蔽无内容路径 | 同上 |
| `404.html` | 自定义错误页，避免默认 404 页被收录 | 手工维护 |
| `og-image.png` | 分享预览图 | `python tools/make_og_image.py` |

生成器是**目录驱动**的：它遍历发布根目录里真实存在的 `.html` 文件，
所以以后新增页面（如 `news/2026-10.html`）只要放进根目录，重跑脚本就会自动收录，
不需要手工维护页面清单。

收录规则：
- 只收录真实存在的 HTML 页面
- 排除 `404.html`、`template.html` 与 `tools/`、`dist/`、`assets/` 等非内容目录
- 站内 `#about` 这类锚点是**页内导航**，不构成独立可索引 URL，因此不进 sitemap
  （这也是 Google 的明确要求：sitemap 中的 URL 不得含 fragment）

## 自定义域名

**步骤概览**（详细 DNS 记录类型、TXT 验证、证书签发与排错见 `CNAME.example`）：

1. 在域名服务商处添加解析：子域名用 `CNAME → tchao8820.github.io`；
   根域名用 4 条 `A` 记录指向 `185.199.108.153 / .109.153 / .110.153 / .111.153`
2. GitHub 仓库 → `Settings` → `Pages` → `Custom domain` 填域名 → `Save`，
   等出现 "DNS check successful"
3. 确认 `https://你的域名` 能打开后，勾选 `Enforce HTTPS`
   （证书由 Let's Encrypt 自动签发，通常 5–15 分钟，最长 24 小时）
4. 域名确认可用后，一键同步所有域名相关位置：

```bash
python tools/set_site_url.py --site-url https://你的域名 --write-cname
git add -A && git commit -m "chore: 切换到自定义域名" && git push
```

> ⚠️ **顺序不能反**。只要仓库根目录出现 `CNAME` 文件，GitHub 会立刻把
> `tchao8820.github.io/ctbu-kexie-website/` 做 301 跳转到该域名；
> 若域名 DNS 还没配好，原地址会直接打不开。要回退就去掉 `--remove-cname` 重跑。

`set_site_url.py` 会自动改这些位置（共 10 处）：

- `index.html`：`<link rel="canonical">`、`og:url`、`og:image`、`twitter:image`、
  JSON-LD 结构化数据里的 `@id` / `url` / `logo`
- `sitemap.xml`：全部 `<loc>`
- `robots.txt`：`Sitemap:` 行
- `CNAME`：按需生成

## 关联的其它发布通道

同一份 `index.html` 同时发布在另外两条通道，互为备份：

| 通道 | 地址 | 状态 |
|---|---|---|
| GitHub Pages | `https://tchao8820.github.io/ctbu-kexie-website/` | 主通道 |
| WorkBuddy 托管 | `https://ctbu-sta.app.workbuddy.host/` | 可用 |
| EdgeOne Makers | 项目 `ctbu-kexie-website` | 已部署，预览链接 3 小时过期，需绑已备案域名才能稳定访问 |

任一通道故障时，其余通道仍可正常访问。

## 内容来源与免责说明

- 文字内容取自协会归档文件：社团章程、协会简介、社团注册登记表、科创月统计表、新闻稿原件。
- 会员数据仅以聚合形式呈现（总数、学院分布），**不含任何学号或个人信息**。
- 页内「入会登记」表单为纯前端生成文本，不向服务器发送数据。
- 公告栏为静态文案，更新需改源码并重新发布。
- 联系方式取自《社团注册登记表》，用于公开咨询。

## 版权

© 重庆工商大学科技协会 CTBU-STA
