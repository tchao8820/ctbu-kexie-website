# 重庆工商大学科技协会官网（CTBU-STA）

> 科技点燃梦想，创新赋能未来

本仓库是重庆工商大学科技协会官网的**源码与发布产物**，用于 **GitHub Pages** 静态托管。

线上地址：<https://tchao8820.github.io/ctbu-kexie-website/>

---

## 仓库结构

```
content/site.json        ★ 内容数据层：全站唯一的内容来源（JSON）
tools/template.html      ★ 页面模板：含迷你 mustache 占位符
tools/build.py           ★ 构建脚本（Python，权威实现）
tools/render.js          ★ 同一套渲染逻辑的 JS 实现（供编辑器浏览器端预览）
tools/check_site.py      ★ 一致性校验（结构/明细/联动/资源/占位符/构建/SEO）
tools/gen_seo.py         生成 sitemap.xml、robots.txt、robots.host.txt
tools/gen_og_image.py    生成社交分享卡片 og-image.png（1200×630）
tools/set_site_url.py    换域名时一键同步全部域名相关位置
tools/_migrate.py        一次性引导脚本：把旧 index.html 抽出成 site.json + template.html
index.html               构建产物：直接发布到 GitHub Pages（勿手工编辑）
editor.html              在线内容编辑器（编辑 site.json，不是改 HTML）
404.html                 自定义 404 错误页
sitemap.xml              站点地图（自动生成，勿手工编辑）
robots.txt               爬虫规则（仓库内版本，自动生成）
robots.host.txt          爬虫规则（主机根版本，自动生成，需另行部署）
og-image.png             社交分享卡片 1200×630
assets/img/              站点图片资源（11 个文件）
CNAME.example            CNAME 模板，绑定自定义域名时参考
.nojekyll                阻止 GitHub Pages 走 Jekyll 构建
.github/workflows/ci.yml CI：校验 + 自动重建 + 产物核对
LICENSE                  源代码许可（MIT）
LICENSE-CONTENT.md       内容与图片许可（CC BY-NC-SA 4.0）
```

### 构建链

```
content/site.json  ─┐
                    ├─→ tools/build.py  ─→ index.html  ─→ GitHub Pages
tools/template.html ┘
```

- **零运行时依赖**：构建只需 Python 3（标准库），不需要 Node、npm 包或任何环境变量。
- **零接口调用**：网站本身是纯静态单页，发布即上线，不需要后端。
- `index.html` 是**提交进仓库的构建产物**，保证「没有构建环境也能直接部署」。
- `tools/render.js` 是 `build.py` 的等价 JS 实现，两个产物**逐字节一致**（CI 会核对），
  这样浏览器里的编辑器也能在本地实时预览最终 HTML，无需后端。

---

## 视觉规范

设计方向是**学术年报**：纸（象牙白 `#FBF9F4`）＋ 墨（深墨蓝 `#14243A`）＋ 一点低饱和深青
（`#0E6E6E`）。刻意不用渐变、阴影与圆角——层次全部由字阶、留白和 1px 细规则线建立。

| 项 | 约定 |
|---|---|
| 字体 | 衬线（思源宋体 / 宋体）用于标题；系统无衬线用于正文；等宽用于数字与英文标签 |
| 章节头 | 统一「编号 01–09 ＋ 英文标签 ＋ 衬线标题」三件套，形成年报式阅读节奏 |
| 数据 | 一律等宽字体、右对齐、`tabular-nums`；合计与比率由构建脚本算出，不手填 |
| 分隔 | 1px `--rule` 细线分组，2px `--ink` 粗线标记报表区（统计条、联系表） |
| 强调 | 深青只用于：章节编号下的英文标签、链接、时间轴节点、图表条形 |

改配色只需动两处：`tools/template.html` 的 `:root` 令牌，以及
`tools/gen_og_image.py` 顶部的色值常量——分享卡片是 Pillow 画的，读不到 CSS，必须手工同步。

---

## 如何更新内容

### 方式一：改 JSON + 构建（推荐）

```bash
# 1. 编辑 content/site.json
# 2. 构建
python tools/build.py

# 3. 一致性自检（可选，CI 也会跑）
python tools/check_site.py

# 4. 提交
git add -A && git commit -m "content: 更新赛事成绩" && git push
```

改完 `content/site.json` 后**必须**重跑 `python tools/build.py`，否则 `index.html`
还是旧内容，CI 会因此报错。

### 方式二：用在线编辑器（不用装工具）

见下方「在线编辑」一节。编辑器改的也是 `content/site.json`，上传后 CI 会自动重建
`index.html`，无需手工跑构建脚本。

### 方式三：改结构或样式

样式、布局、脚本改动属于**代码改动**，应直接改 `tools/template.html`，
然后重跑 `python tools/build.py`。不要直接编辑 `index.html`——下次构建会被覆盖。

### 数据联动：合计与获奖率不需要手填

`sections.results.rows` 里每一项赛事只填 4 个数字：

| 字段 | 含义 |
|---|---|
| `signupGroups` | 报名组数 |
| `signupPeople` | 报名人次 |
| `awardGroups` | 获奖组数 |
| `awardPeople` | 获奖人次 |

下面这些**全部由构建脚本自动计算**，在 `site.json` 里用 `{占位符}` 引用即可：

| 占位符 | 含义 | 来源 |
|---|---|---|
| `{count}` | 赛事项数 | `rows` 条数 |
| `{signupGroups}` / `{signupPeople}` | 报名合计（组 / 人次） | `rows` 求和 |
| `{awardGroups}` / `{awardPeople}` | 获奖合计（组 / 人次） | `rows` 求和 |
| `{rateByGroup}` / `{rateByPeople}` | 获奖率（按组 / 按人次，%） | 获奖 ÷ 报名 |
| `{memberCount}` | 会员总数 | `sections.member.kpis[0].value` |
| `{memberRatio}` | 机械学院占比（%） | `kpis[3] ÷ kpis[0]` |
| `{topAwardGroups}` / `{topAwardPeople}` / `{topAwardRatio}` | 获奖人次最多赛事的组数 / 人次 / 占比 | `rows` 中获奖人次最大者 |

> ⚠️ **不要在文案里手写「共 20 项」「2953 人次」这类数字。**
> 手写会导致改动明细后总数对不上，`check_site.py` 会直接报 ERROR。

---

## 模板语法（迷你 mustache）

`tools/template.html` 支持以下语法：

| 语法 | 作用 |
|---|---|
| `{{path.to.value}}` | 取值并 HTML 转义（`& < > "`） |
| `{{$path}}` | 取值且**不转义**，用于构建期生成的原始 HTML 片段 |
| `{{#path}}…{{/path}}` | 区块：列表→逐项迭代，字典→压栈，字符串/布尔→条件成立时输出 |
| `{{^path}}…{{/path}}` | 反向区块：值为空时输出 |
| `{key}` | 派生值占位符，见上表 |

- 已有的 HTML 实体（`&ensp;` `&amp;` 等）在转义时会被**原样保留**，不会被二次转义成
  `&amp;ensp;`。
- 每个含列表的键会自动获得一个布尔量 `has<Key>`（如 `hasItems`、`hasKpis`），
  模板里可直接用 `{{#hasItems}}…{{/hasItems}}` 判断列表是否为空。
- 路径解析遵循 mustache 规则：先按完整路径在上下文栈里找，再退到最长公共前缀。

---

## 一致性校验与 CI

```bash
python tools/check_site.py            # 全量校验
python tools/check_site.py --verbose  # 打印每一项检查结果
```

校验内容分 8 组：

| 组 | 检查什么 | 级别 |
|---|---|---|
| A 结构 | 36 个必需字段是否存在、类型是否正确 | ERROR |
| B 明细 | 数字非负整数；获奖组数 > 报名组数 | ERROR / WARN |
| C 联动 | 11 处汇总文案**必须**使用 `{占位符}`，不能写死数字 | ERROR |
| D 资源 | `assets/img/` 下每张被引用的图片真实存在 | ERROR |
| E 占位符 | 所有 `{key}` 都是已知派生键 | ERROR |
| F 构建 | `python tools/build.py --check`（产物与数据一致） | ERROR |
| G 渲染 | `node tools/render.js --check`（JS 产物与 Python 一致） | ERROR |
| H SEO | `sitemap.xml` / `robots.txt` / `robots.host.txt` 与当前域名一致 | ERROR |

退出码：`0` 通过（有 WARN 也算通过），`1` 有 ERROR。

### GitHub Actions

`.github/workflows/ci.yml` 在 push / PR 到 `main` 时自动运行三个作业：

| 作业 | 触发 | 做什么 |
|---|---|---|
| `data-check` | 总是 | 跑 `check_site.py`（跳过构建与 SEO 项），任一 ERROR 即失败 |
| `rebuild` | 仅 push 到 `main` | 重新生成 `index.html` / `sitemap.xml` / `robots.txt`，有差异就自动提交 |
| `verify` | 仅 PR | 跑完整 `check_site.py`（含构建、渲染、SEO 全项） |

`rebuild` 作业会把重建后的产物以 `github-actions[bot]` 的身份提交回 `main`，
因此**只改 `content/site.json` 并 push，内容会自动上线**，不需要本地装 Python。

> 若仓库设置了分支保护（禁止 bot 推送），需要允许 Actions 写入 `contents` 权限，
> 或改为本地跑 `python tools/build.py` 后一并提交。

---

## 在线编辑

仓库内 `editor.html` 用于**不用写代码、不用装工具**地在线修改网站内容。

### 打开方式

**方式一（推荐，需能开 HTTP 服务）**

```bash
python -m http.server 8000
```

然后浏览器访问 <http://localhost:8000/editor.html>

**方式二（已部署，直接访问）**

<https://tchao8820.github.io/ctbu-kexie-website/editor.html>

> ⚠️ **不能直接双击 `editor.html` 打开**（`file://` 协议下浏览器禁止读取同目录文件）。

### 能改什么

编辑器直接编辑 `content/site.json`，覆盖 13 个分组：

| 分组 | 内容 |
|---|---|
| 站点地址与 SEO | 站点 URL、OG 图、logo、标题/描述/关键词 |
| 导航栏 | 品牌名、CTA、导航链接（可增删） |
| 首页横幅 | 标语、副标语、英文全称、成立说明、3 个数字块 |
| 协会简介 | 标题、导语、正文段落 |
| 协会历程 | 9 条时间线（可增删）；年份/标题/描述/徽章 |
| 组织架构 | 4 个部门（可增删）、负责人、指导教师、专项小组 |
| 科创月赛事成绩 | 20 项赛事（可增删）；**只填 4 个数字，合计与获奖率自动重算** |
| 成员风采 | 4 个 KPI、学院分布 |
| 新闻动态与公告 | 5 条新闻（可增删）；日期/分类/标题/正文 |
| 活动与项目 | 6 个活动（可增删） |
| 加入协会 | 步骤、福利 |
| 联系方式 | 4 项（可增删）；标签/内容/说明/链接 |
| 页脚 | 版权行、来源说明、页脚导航 |

### 实时统计面板

编辑器右侧顶部有一块**实时统计**，随输入即时重算：
赛事项数、报名组数、报名人次、获奖组数、获奖人次、获奖率（按组 / 按人次）、
会员人数、机械学院占比。

若某项赛事出现「获奖 > 报名」，面板会给出橙色警告提示——通常是原件统计口径问题，
需要在文案里补口径说明，而不是直接改数。

### 用法

1. 左侧点分组跳转，直接在右侧改文字
2. 带 **＋** 的按钮可新增条目，条目右上角 **✕** 可删除
3. 改完点右上 **预览效果**，用真实渲染结果检查排版
4. 点 **生成新版**，弹窗提供两个下载：

   | 按钮 | 文件 | 上传到 | 之后 |
   |---|---|---|---|
   | **下载 site.json**（主） | `content/site.json` | <https://github.com/tchao8820/ctbu-kexie-website/edit/main/content/site.json> | CI 自动重建 `index.html` 并上线 |
   | 下载构建好的 index.html（次） | `index.html` | <https://github.com/tchao8820/ctbu-kexie-website/edit/main/index.html> | 直接上线（绕过 CI 重建） |

快捷键：`Ctrl+S` 生成导出，`Esc` 关闭弹窗。

### 重要限制

- 这是**静态页面，没有服务器数据库**。改动不会自动保存，也不会自动上线，
  **必须在生成后完成上传**。刷新页面会丢失未导出的改动。
- 编辑器**不修改图片**。换图需手动替换 `assets/img/` 下的文件。
- 只改内容，**不要用它改样式或结构** —— 那是代码改动，应改 `tools/template.html` 并走 git 提交。

---

## 搜索引擎优化

| 文件 | 作用 | 生成方式 |
|---|---|---|
| `sitemap.xml` | 向搜索引擎提交全部公开页面 | `python tools/gen_seo.py` |
| `robots.txt` | 仓库内版本（子路径用） | 同上 |
| `robots.host.txt` | 主机根版本（**爬虫真正读的那份**） | 同上 |
| `404.html` | 自定义错误页，避免默认 404 页被收录 | 手工维护 |
| `og-image.png` | 分享预览图 1200×630 | `python tools/gen_og_image.py`（改配色请同步脚本内的色值常量） |

生成器是**目录驱动**的：它遍历发布根目录里真实存在的 `.html` 文件，
所以以后新增页面（如 `news/2026-10.html`）只要放进根目录，重跑脚本就会自动收录，
不需要手工维护页面清单。

收录规则：
- 只收录真实存在的 HTML 页面
- 排除 `404.html`、`editor.html`、`tools/`、`content/`、`dist/`、`assets/` 等非内容目录
- 站内 `#about` 这类锚点是**页内导航**，不构成独立可索引 URL，因此不进 sitemap
  （这也是 Google 的明确要求：sitemap 中的 URL 不得含 fragment）

### robots.txt 与主机根（重要）

爬虫**只读主机根目录的 robots.txt**。Google 官方文档明确：
`https://example.com/robots.txt` 有效，而 `https://example.com/folder/robots.txt`
→「不是有效的 robots.txt 文件，抓取工具不会检查子目录中的 robots.txt」。

本站位于 `https://tchao8820.github.io/ctbu-kexie-website/`，位于**子路径**，
因此本仓库内的 `robots.txt` 虽可下载，但爬虫不会读取。

`tools/gen_seo.py` 现在会**同时生成两份**：

| 文件 | 用途 | 部署位置 |
|---|---|---|
| `robots.txt` | 仓库内版本（路径不带前缀） | 本仓库根目录 |
| `robots.host.txt` | 主机根版本（路径带 `/ctbu-kexie-website` 前缀） | **用户站仓库根目录** / 自定义域名根目录 |

主机根文件应放到 [`tchao8820.github.io`](https://github.com/tchao8820/tchao8820.github.io)
仓库的根目录，对 `tchao8820` 名下所有 Pages 项目页生效。

| 项 | 状态 | 说明 |
|---|---|---|
| `Allow: /`（允许抓取） | ✅ 生效 | 主机根 robots.txt 已存在 |
| `Disallow:` 各条 | ✅ 生效 | 已按主机根视角自动补 `/ctbu-kexie-website` 前缀 |
| `Sitemap:` 声明 | ✅ 可自动发现 | 爬虫现在能读到该行 |

> 绑定自定义域名后，主机根 robots.txt 需要重新部署到域名根目录；
> `python tools/set_site_url.py` 会一并重算 `robots.host.txt` 的前缀。

> ⚠️ **不要**屏蔽 `/assets/`——那是真实图片目录，屏蔽后 `og:image` 与正文配图
> 将无法被抓取，影响图片搜索收录。

> 手动提交 sitemap（免费，各平台一次即可）：
> Google Search Console / Bing Webmaster Tools / 百度搜索资源平台，添加站点后提交
> `https://tchao8820.github.io/ctbu-kexie-website/sitemap.xml`

---

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

`set_site_url.py` 改的是**数据源**（`content/site.json` 里的 `site.url`），
然后自动重跑构建与 SEO 生成，因此以下位置会一并更新：

- `content/site.json`：`site.url`（`og:image` / `logo` / `canonical` 都由它派生）
- `index.html`：`<link rel="canonical">`、`og:url`、`og:image`、`twitter:image`、
  JSON-LD 结构化数据里的 `@id` / `url` / `logo`
- `sitemap.xml`：全部 `<loc>`
- `robots.txt` / `robots.host.txt`：`Sitemap:` 行与路径前缀
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

---

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
git push gitee main                       # 推送镜像
# 然后浏览器：仓库 → 服务 → Gitee Pages → 分支选 main、目录选 / → 点「启动」
```

之后每次更新内容，都要 **push 后再回 Gitee Pages 页面点一次「更新」**（免费版不会自动重新部署）。

> SEO 口径：Gitee 只是镜像，**`canonical` 与 sitemap 仍统一指向 GitHub Pages**，
> 不改域名相关文件，避免两站重复内容分散权重。

---

## 内容来源与免责说明

- 文字内容取自协会归档文件：社团章程、协会简介、社团注册登记表、科创月统计表、新闻稿原件。
- 会员数据仅以聚合形式呈现（总数、学院分布），**不含任何学号或个人信息**。
- 页内「入会登记」表单为纯前端生成文本，不向服务器发送数据。
- 公告栏为静态文案，更新需改 `content/site.json` 并重新发布。
- 联系方式取自《社团注册登记表》，用于公开咨询。

### 数据口径说明

赛事成绩表的「报名数」与「获奖数」分别以报名表原件、获奖名单原件为准。
其中 3D 打印大赛（三赛道合计）获奖 149 人次、报名 148 人次，差 1 人次来自
两份原件的统计口径差异——**按原件数值呈现，不作调整**，并在页面上以脚注注明。

---

## 许可与版权

| 范围 | 许可 |
|---|---|
| 源代码与工具（`tools/`、`editor.html`、`.github/`） | [MIT](LICENSE) |
| 内容与图片（`content/site.json`、`assets/img/`、页面文案） | [CC BY-NC-SA 4.0](LICENSE-CONTENT.md) |

© 重庆工商大学科技协会 CTBU-STA
