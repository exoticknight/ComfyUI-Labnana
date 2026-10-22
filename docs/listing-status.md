# ComfyUI-Labnana 收录申请清单（Listing Status）

> 目标：调研 ComfyUI 生态中所有可收录 ComfyUI-Labnana 的榜单（排行榜）、Awesome 列表、市场与目录，并逐个提交收录申请。
> 最后更新：2026-10-22（UTC）

## 一、官方渠道（✅ 已完成）

| 渠道 | 状态 | 说明 |
|---|---|---|
| [Comfy Registry](https://registry.comfy.org/publishers/exoticknight/nodes/comfyui-labnana) | ✅ 已发布 v2.0.4 | 官方节点市场；`Publish to Comfy registry` 流水线最近 5 次全部成功（最后 2026-08-22） |
| [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager) | ✅ 自动收录 | 已上 Registry 的节点会被 Manager 自动收录，无需再改 `custom-node-list.json` |
| [ComfyUI Frontend registry-census](https://github.com/Comfy-Org/ComfyUI_frontend) | ✅ 已在册 | `scripts/registry-census/corpus.pins.json` 已包含 comfyui-labnana |

## 二、自动同步目录（无需申请，源自 Registry / Manager 数据）

| 渠道 | 说明 |
|---|---|
| [ComfyUI-Workflow/awesome-comfyui](https://github.com/ComfyUI-Workflow/awesome-comfyui)（734⭐） | README 数据每日从 ComfyUI Manager 自动抓取，无需提交 |
| [jalberty2018/awesome-comfyui](https://github.com/jalberty2018/awesome-comfyui) | 数据每日从 Registry + Manager 自动抓取（"added to catalog today" 列表），无需提交 |
| [vramdb.com](https://vramdb.com/) | 节点目录，自动同步 Registry/Manager |
| [runcomfy.com/comfyui-nodes](https://www.runcomfy.com/comfyui-nodes) | 节点目录（15152 节点 / 1458 扩展，每日更新），自动同步 |
| [comfyuiweb.com/extensions](https://comfyuiweb.com/extensions) | 扩展目录，自动同步 |
| [comfyui-wiki.com](https://comfyui-wiki.com/en/resource/custom-nodes) | 自定义节点文档站，按 pinned source 自动扫描（页面生成待确认） |
| Ecosyste.ms Awesome 镜像 | GitHub 自动镜像，无需申请 |

## 三、主动提交（PR / 申请）——逐个执行

| # | 渠道 | 状态 | PR 链接 |
|---|---|---|---|
| 1 | GitHub 仓库 topics（comfyui, comfyui-custom-node, comfyui-nodes, image-generation, text-to-image, ai-art, api-wrapper） | ✅ 已完成 2026-08-22 | — |
| 2 | [lucianosb/awesome-comfyui](https://github.com/lucianosb/awesome-comfyui)（212⭐，"Custom Nodes and Plugins" 段落） | ✅ 已收录 2026-08-26 | [lucianosb/awesome-comfyui#13](https://github.com/lucianosb/awesome-comfyui/pull/13) |
| 3 | [WASasquatch/comfyui-plugins](https://github.com/WASasquatch/comfyui-plugins)（README 明确 "Feel free to PR your own plugins"，EN/CN/JP 三份） | ✅ 已提交 PR，待合并 | [WASasquatch/comfyui-plugins#17](https://github.com/WASasquatch/comfyui-plugins/pull/17) |
| 4 | [602387193c/ComfyUI-wiki](https://github.com/602387193c/ComfyUI-wiki)（1150⭐，中文 Wiki「👍custom nodes排行榜」） | ✅ 已提交 PR，待合并 | [602387193c/ComfyUI-wiki#11](https://github.com/602387193c/ComfyUI-wiki/pull/11) |

> PR 合并后，可将本清单中对应状态改为"已收录"。合并需要各仓库维护者确认；如长时间未响应，可考虑在对应仓库提 Issue 跟进。

## 四、需人工操作（社区渠道，草稿见下）

| 渠道 | 说明 | 操作人 |
|---|---|---|
| [Reddit r/comfyui](https://www.reddit.com/r/comfyui/) | 该版块禁止纯广告，需以"帮助性展示"形式发帖（草稿见附录 A） | 用户 |
| [ComfyUI Discord](https://discord.gg/comfyui)（官方） | 官方 Discord 展示区公告（草稿见附录 B） | 用户 |
| 工作流市场：Civitai / comfyworkflows.com / OpenArt | 可上传 `example_workflows/` 中 4 个示例工作流（可选，需各平台账号） | 用户 |

---

## 附录 A：Reddit r/comfyui 展示帖草稿

标题：`[Showcase] ComfyUI-Labnana — one node for Gemini 3 Pro / GPT-Image-2.5 / Wan2.7 / Seedream image APIs`

正文：

> I built an open-source ComfyUI custom node set for the Labnana (Marswave) image-generation API. A single node covers text-to-image, image editing (up to 14 reference images) and 4K output — submit, wait and download all happen inside the node. It also ships cost-control tools (credit estimation before spending, subscription balance) and an async task API for batch pipelines.
>
> - Models: gemini-3-pro-image, gemini-3.1-flash-image, gpt-image-2, gpt-image-2.5-flare, gpt-image-2.5-sunburst, wan2.7-image(-pro), seedream-5-0-pro
> - Install: ComfyUI-Manager → search "Labnana", or `comfy node registry-install comfyui-labnana`
> - Repo: https://github.com/exoticknight/ComfyUI-Labnana · Registry: https://registry.comfy.org/publishers/exoticknight/nodes/comfyui-labnana
>
> Happy to answer questions. Feedback welcome!

## 附录 B：ComfyUI Discord 公告草稿

> **NEW: ComfyUI-Labnana** 🎨 — ComfyUI custom nodes for the Labnana image generation API.
> - One node: text-to-image / image editing / 4K — submit, wait, download all in-node
> - Models: Gemini 3 Pro Image, Gemini 3.1 Flash, GPT-Image-2, GPT-Image-2.5 Flare and Sunburst, Wan2.7 Image (Pro), Seedream 5.0 Pro
> - Cost control: credit estimate + subscription balance nodes, fail-fast parameter validation
> - Async task API for batch pipelines
> - Install via Manager (search "Labnana") or `comfy node registry-install comfyui-labnana`
> - https://github.com/exoticknight/ComfyUI-Labnana
