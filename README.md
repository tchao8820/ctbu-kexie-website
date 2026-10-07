# 重庆工商大学科技协会官网（CTBU-STA）

> 科技点燃梦想，创新赋能未来

本仓库是重庆工商大学科技协会官网的发布源码，用于 **GitHub Pages** 静态托管。

线上地址：<https://tchao8820.github.io/ctbu-kexie-website/>

## 仓库内容

```
index.html        官网全部内容（单文件，含内联样式与脚本；图片为外链）
404.html          自定义 404 错误页（GitHub Pages 自动启用，已被 robots 屏蔽）
sitemap.xml       站点地图（自动生成，勿手工编辑）
robots.txt        爬虫规则 + sitemap 声明（自动生成，勿手工编辑）
og-image.png      社交分享卡片 1200×630（微信 / QQ / Twitter 预览用）
assets/img/       站点图片资源（11 个文件，由 index.html 引用）
CNAME.example     CNAME 文件模板，绑定自定义域名时参考（当前未启用）
.nojekyll         阻止 GitHub Pages 走 Jekyll 构建，保证原样发布
tools/gen_seo.py        扫描发布目录，自动生成 sitemap.xml 与 robots.txt
tools/set_site_url.py   换域名时一键同步全部域名相关位置
README.md         本说明
```

官网是**静态单页站点**：零接口调用、零构建步骤、无需任何环境变量，
因此发布方式就是「把文件放好」，没有构建过程。

### 为什么图片是外链而不是内嵌

早期版本把全部图片以 base64 写进 `index.html`，且为实现点击放大灯箱，
每张图在 `data-img` 与 `src` 两处各存一份完整数据。结果：

| 问题 | 数值 |
|---|---|
| 单页体积 | 2.30 MB（gzip 后 1.70 MB，base64 几乎不可压缩） |
| 重复内嵌 | 10 组图片字节完全相同，冗余 987 KB（占43.8%） |
| `loading="lazy"` | **完全失效**——浏览器须下载整个文件才能解析 |
| `fetchpriority="high"` | hero 图排在第 659 行，反成最后到达的资源，实测首字节 13.5 s |

现已改为 `assets/img/` 下的独立文件 + 相对路径：

| 指标 | 改前 | 改后 |
|---|---|---|
| `index.html` | 2,304,700 B | 约 93 KB |
| 首屏传输 | 1.70 MB（gzip） | 约 93 KB + 首图 140 KB，且可并行 |
| `loading="lazy"` | 无效 | 真正生效，滚动到才加载 |
| 二次访问 | 重下 1.7 MB | 图片走独立缓存 |

代价是「零外部请求」变为「有限外部请求」，这个取舍值得。
另：favicon（64×64，8 KB）仍保持内联——图标极小，内联可省一次请求。

> 图片重命名后请同步更新 `index.html` 中 `src` 与 `data-img` 两处引用，
> 两者必须指向同一文件（灯箱直接读取 `data-img` 作为 `<img>` 的 src）。

## 如何更新内容

> ⚠️ **本仓库只存发布产物，不含完整构建链。**
> 下面步骤 1–2 依赖本机 `F:\科技协会官网\` 目录下的模板与 `build_site.py`
> （未入库，因为含本机绝对路径）。换机器维护需先取得该目录。

1. 修改源模板 `F:\科技协会官网\template.html`
2. 在 `F:\科技协会官网\` 下重建：`python F:\.workbuddy\scan\build_site.py`
3. 把新的 `index.html` 覆盖到本仓库根目录
4. 若图片有增删改名，同步更新 `assets/img/`
5. 重新生成 SEO 文件：`python tools/gen_seo.py`
6. 提交并推送，GitHub Pages 会在 1–2 分钟内自动更新

> 站点上线后 `lastmod` 想刷新，只需重跑 `tools/gen_seo.py`。
> 改动图片后请自查：`grep -o 'assets/img/[^"]*' index.html | sort -u`
> 列出的每个文件都必须真实存在，否则会出现破图。

## 搜索引擎优化

| 文件 | 作用 | 生成方式 |
|---|---|---|
| `sitemap.xml` | 向搜索引擎提交全部公开页面 | `python tools/gen_seo.py` |
| `robots.txt` | 允许全站抓取 + 声明 sitemap + 屏蔽无内容路径 | 同上 |
| `404.html` | 自定义错误页，避免默认 404 页被收录 | 手工维护 |
| `og-image.png` | 分享预览图1200×630 | 手工制作，当前仓库未收录其生成脚本 |

生成器是**目录驱动**的：它遍历发布根目录里真实存在的 `.html` 文件，
所以以后新增页面（如 `news/2026-10.html`）只要放进根目录，重跑脚本就会自动收录，
不需要手工维护页面清单。

收录规则：
- 只收录真实存在的 HTML 页面
- 排除 `404.html`、`template.html` 与 `tools/`、`dist/`、`assets/` 等非内容目录
- 站内 `#about` 这类锚点是**页内导航**，不构成独立可索引 URL，因此不进 sitemap
  （这也是 Google 的明确要求：sitemap 中的 URL 不得含 fragment）

### ⚠️ 当前 robots.txt 的一处限制（重要）

爬虫**只读主机根目录的 robots.txt**。Google 官方文档明确：
`https://example.com/robots.txt` 有效，而 `https://example.com/folder/robots.txt`
「不是有效的 robots.txt 文件，抓取工具不会检查子目录中的 robots.txt」。

本站现在位于 `https://tchao8820.github.io/ctbu-kexie-website/`，
即项目页位于**子路径**，所以：

| 项 | 现状 | 说明 |
|---|---|---|
| `Allow: /`（允许抓取） | 实际已生效 | 主机根 `https://tchao8820.github.io/robots.txt` 返回 404，等于「无限制」 |
| `Disallow:` 各条 | **暂不生效** | 子路径下的规则不会被读取 |
| `Sitemap:` 声明 | **暂不自动发现** | 需手动提交（见下） |

**三种解决方式**（任一即可）：

1. **绑定自定义域名（推荐）** —— 绑好后本站就位于域名根目录，
   `https://你的域名/robots.txt` 立即全部生效。见下一节。
2. **建一个用户站仓库** `tchao8820.github.io`，里面只放一份 robots.txt，
   它就会成为 `tchao8820.github.io` 主机根目录的 robots.txt，覆盖所有项目页：

   ```bash
   # 新建仓库 tchao8820.github.io（公开），根目录放 robots.txt：
   #   User-agent: *
   #   Allow: /
   #   Disallow: /ctbu-kexie-website/404.html
   #   Sitemap: https://tchao8820.github.io/ctbu-kexie-website/sitemap.xml
   ```

3. **什么都不做** —— 影响很小：`404.html` 已带 `<meta name="robots" content="noindex,nofollow">`，
   索引层面已被挡住；sitemap 手动提交一次也能被收录。

> 手动提交 sitemap（免费，各平台一次即可）：
> Google Search Console / Bing Webmaster Tools / 百度搜索资源平台，添加站点后提交
> `https://tchao8820.github.io/ctbu-kexie-website/sitemap.xml`

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

### 免费域名从哪来

| 渠道 | 拿到什么 | 特点 | 建议 |
|---|---|---|---|
| **GitHub 学生包** | Namecheap 免费 `.me` 域名 1 年（另有 `.tech` 1 年、Name.com 25+ 后缀可选） | **真正的顶级域名**，可自由转移、自带 SSL | ⭐ 首选，用 edu.cn 邮箱或学信网证明认证 |
| **EU.org** | `xxx.eu.org` | 1996 年运营至今，免费终身，支持完整 DNS | 次选，审核 1–4 周 |
| **FreeDNS (afraid.org)** | `xxx.mooo.com` 等公共子域 | 注册快，免费版限 50 条记录 | 临时用 |
| **DuckDNS** | `xxx.duckdns.org` | 秒开，主要用于家宽动态 IP | 不推荐绑站点 |
| No-IP | `xxx.ddns.net` | 需每 30 天手动确认一次 | 不推荐 |
| ~~Freenom~~ | ~~`.tk/.ml/.ga`~~ | **已停止新注册**，勿用 | 避开 |

其余免费「域名」本质是平台子域：`*.pages.dev`（Cloudflare）、`*.vercel.app`、
`*.netlify.app` —— 换了等于换托管，与 GitHub Pages 无关。

> GitHub Pages 要求自定义域名**在整个 GitHub Pages 体系内唯一**。
> 免费共享子域（如 DuckDNS）实践中有绑定失败的案例，权威做法是用你能完全控制
> DNS 的域名（学生 `.me` 或 `xxx.eu.org`）。

## 关联的其它发布通道

同一份 `index.html` 同时发布在多处，互为备份：

| 通道 | 地址 | 状态 |
|---|---|---|
| GitHub Pages | `https://tchao8820.github.io/ctbu-kexie-website/` | ✅ 主通道（canonical 指向此处） |
| WorkBuddy 托管 | `https://ctbu-sta.app.workbuddy.host/` | ✅ 可用 |
| Gitee Pages | `https://tong-chao8864.gitee.io/ctbu-kexie-website/` | ⏳ 待开通（仓库建成后一键推送） |
| EdgeOne Makers | 项目 `ctbu-kexie-website` | ⚠️ 预览链接 3 小时过期，需绑已备案域名 |

任一通道故障时，其余通道仍可正常访问。

### Gitee Pages（国内访问通道）

Gitee 有对标 GitHub Pages 的 **Gitee Pages**，免费、服务器在国内，国内访问速度明显优于 GitHub Pages。
本站 `gitee` 远端已配好（`git@gitee.com:tong-chao8864/ctbu-kexie-website.git`，SSH 已验证连通）。

**与 GitHub Pages 的关键差异**（决定了怎么用它）：

| 项 | GitHub Pages | Gitee Pages |
|---|---|---|
| 仓库要求 | 公开 | **必须公开**，且账号需**实名认证** |
| 自动部署 | push 后自动生效 | **每次 push 必须回后台点「更新」** |
| 默认地址 | `用户名.github.io/仓库名` | `用户名.gitee.io/仓库名` |
| 自定义域名 | 免备案即可 | **需域名已 ICP 备案** |
| HTTPS | Let's Encrypt 自动签发 | 以控制台页面提示为准 |
| 内容审核 | 无 | 有合规审核，禁止违规内容与商业广告 |

**开通步骤（人工，共 3 步）**

1. 在 Gitee 网页新建**公开**仓库 `ctbu-kexie-website`（**不要勾选初始化 README**，保持空仓库）
2. 首次使用按提示完成**实名认证**（通常 1 个工作日内审核）
3. 本地推送并开通服务：

```bash
cd F:/科技协会官网/github-pages
git push gitee main                       # 推送镜像
# 然后浏览器：仓库 → 服务 → Gitee Pages → 分支选 main、目录选 / → 点「启动」
```

之后每次更新内容，都要 **push 后再回 Gitee Pages 页面点一次「更新」**（免费版不会自动重新部署）。

> SEO 口径：Gitee 只是镜像，**`canonical` 与 sitemap 仍统一指向 GitHub Pages**，
> 不改域名相关文件，避免两站重复内容分散权重。

## 内容来源与免责说明

- 文字内容取自协会归档文件：社团章程、协会简介、社团注册登记表、科创月统计表、新闻稿原件。
- 会员数据仅以聚合形式呈现（总数、学院分布），**不含任何学号或个人信息**。
- 页内「入会登记」表单为纯前端生成文本，不向服务器发送数据。
- 公告栏为静态文案，更新需改源码并重新发布。
- 联系方式取自《社团注册登记表》，用于公开咨询。

## 版权

© 重庆工商大学科技协会 CTBU-STA
