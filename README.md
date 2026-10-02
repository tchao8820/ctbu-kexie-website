# 重庆工商大学科技协会官网（CTBU-STA）

> 科技点燃梦想，创新赋能未来

本仓库是 [重庆工商大学科技协会](https://ctbu-sta.app.workbuddy.host/) 官网的发布源码，用于 GitHub Pages 静态托管。

## 仓库内容

```
index.html    官网全部内容（单文件，含内联样式、脚本与 base64 图片）
.nojekyll     阻止 GitHub Pages 走 Jekyll 构建，保证原样发布
README.md     本说明
```

官网为**单文件静态站点**：零外部请求、零接口调用、零构建步骤、无需任何环境变量，
因此发布方式就是「把 `index.html` 放好」，没有构建过程。

## 如何更新

1. 修改源文件（源工程在 `F:\科技协会官网\template.html`，改完需重新构建以注入图片）
2. 把新的 `index.html` 覆盖到本仓库根目录
3. 提交并推送，GitHub Pages 会在 1–2 分钟内自动更新

## 关联的其它发布通道

同一份 `index.html` 同时发布在 EdgeOne Pages，两条通道互为备份：

| 通道 | 地址 |
|---|---|
| GitHub Pages | `https://tchao8820.github.io/ctbu-kexie-website/` |
| EdgeOne Pages | `https://ctbu-sta.app.workbuddy.host/` |

任一通道故障时，另一条仍可正常访问。

## 内容来源与免责说明

- 文字内容取自协会归档文件：社团章程、协会简介、社团注册登记表、科创月统计表、新闻稿原件。
- 会员数据仅以聚合形式呈现（总数、学院分布），**不含任何学号或个人信息**。
- 页内「入会登记」表单为纯前端生成文本，不向服务器发送数据。
- 公告栏为静态文案，更新需改源码并重新发布。
- 联系方式取自《社团注册登记表》，用于公开咨询。

## 版权

© 重庆工商大学科技协会 CTBU-STA
