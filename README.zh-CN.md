# ComfyUI-Labnana

中文文档 | [English](README.md)

Labnana(火星电波)图像生成 OpenAPI 的 ComfyUI 自定义节点集。覆盖官方接口的全部能力:同步生图、异步任务(提交 / 轮询 / 历史)、额度预估、订阅查询。

- 接入文档:<https://labnana.com/docs/openapi/guide>
- 完整 API 参考:<https://docs.marswave.ai/openapi-labnana.html>

## 安装

```
cd ComfyUI/custom_nodes
git clone https://github.com/exoticknight/ComfyUI-Labnana.git
```

仅依赖 `requests`(ComfyUI 自带)。重启 ComfyUI 后,节点位于 **Labnana** 分类下。

## API Key

在 <https://labnana.com/api-keys> 创建 Key(`ls_` 开头),二选一:

1. 填入 **Labnana API Client** 节点的 `api_key` 字段;
2. 设置环境变量 `LABNANA_API_KEY`(字段留空时自动读取,推荐,避免 Key 随工作流文件泄露)。

## 节点一览

| 节点 | 分类 | 对应接口 | 说明 |
|---|---|---|---|
| Labnana API Client | Account | — | 配置 Key / 超时 / 重试,输出 `client` 供其他节点复用 |
| Labnana Subscription Info | Account | `GET /user/subscription` | 查询总额度、月度/永久额度、付费状态 |
| Labnana Image Generation | Generate | `POST /images/generation` | 同步生图,直接返回图像(base64),适合交互式使用 |
| Labnana Image Generation (Async) | Generate | `POST /images/generation/async` + 轮询 | 提交后自动轮询并下载结果 URL,4K / 慢任务更稳 |
| Labnana Estimate Credits | Generate | `POST /images/generation/estimate-credits` | 生成前预估消耗额度、检查可行性 |
| Labnana Submit Task | Tasks | `POST /images/generation/async` | 只提交、立即返回 taskId,不等待 |
| Labnana Get Task | Tasks | `GET /images/generation/tasks/{taskId}` | 按 taskId 查询/等待任务并下载图片 |
| Labnana List Tasks | Tasks | `GET /images/generation/tasks` | 分页浏览任务历史,可按状态过滤 |
| Labnana Load Image From URL | Helpers | — | 把结果 URL(或任意图片 URL)加载为 IMAGE |

## 模型与限制

节点里只选 `model`,`provider` 自动推导:

| 模型 | provider | 尺寸 | 参考图上限 | 额度 (1K/2K/4K) |
|---|---|---|---|---|
| gemini-3-pro-image | google | 1K/2K/4K | 14 | 15/15/30 |
| gemini-3.1-flash-image | google | 1K/2K/4K | 14 | 10/10/20 |
| gpt-image-2 | openai | 1K/2K/4K | 4 | 4/6/10 |
| wan2.7-image-pro | alibaba | 1K/2K/4K | 9 | 6/8/12 |
| wan2.7-image | alibaba | 1K/2K | 9 | 4/6 |
| seedream-5-0-pro | bytedance | 1K/2K | 10 | 6/15 |

宽高比:`1:1, 2:3, 3:2, 3:4, 4:3, 9:16, 16:9, 21:9, 1:4, 4:1, 1:8, 8:1`。

不合法组合(如 wan2.7-image 选 4K、参考图超上限)会在发请求前直接报错,不浪费额度。

## 参考图(图生图 / 编辑)

两种方式,可混用,总数受模型上限约束:

- `reference_images`(IMAGE 输入):ComfyUI 图像批次,自动编码为 base64 内联上传(过大自动缩到 3072px 内 / 转 JPEG,规避 20MB 请求体上限);
- `reference_image_urls`(文本):每行一个 `https://` 或 `gs://` URL,以 fileData 方式引用。

## 示例工作流

[example_workflows/](example_workflows) 内置四个开箱即用的工作流,会出现在 ComfyUI 的 **Workflow → Browse Templates → ComfyUI-Labnana** 模板浏览器中(也可直接把 JSON 拖到画布上):

- **Text to Image** — 最简同步生图
- **Image Editing** — 参考图 + `system_prompt` 风格约束
- **Async 4K Generation** — 提交/轮询/下载,适合 4K 慢任务
- **Account & Costs** — 生成前查余额、预估积分、看任务历史

## 典型接法

**文生图**:`Labnana API Client` → `Labnana Image Generation`(填 prompt,选 model/size/ratio)→ `Save Image`。

**图生图/改图**:在上面基础上把 `Load Image` 接到 `reference_images`,prompt 写编辑指令。

**异步长任务**:`Labnana Submit Task` 拿到 `task_id` → 之后任意时刻用 `Labnana Get Task` 取回结果(也可直接用 `Labnana Image Generation (Async)` 一步到位)。

**成本控制**:先接 `Labnana Estimate Credits` 查看 `credits` 与 `can_generate`,再决定是否生成。

**system prompt**:四个生成类节点(同步/异步生图、Submit Task、Estimate Credits)均有可选的 `system_prompt` 输入,用于统一风格/行为指令。API 无原生 system prompt 字段,发送时会拼接在 prompt 前(空行分隔),方便在多个工作流间复用同一段风格约束。

`seed` 参数不会发送给 API,仅用于让 ComfyUI 重新执行节点(否则相同参数会命中缓存直接返回上次结果);设为 randomize 即每次都重新生成。

## 错误处理

| code | 含义 | 处理 |
|---|---|---|
| 21007 | API Key 无效 | 检查 Key 配置 |
| 26004 | 额度不足 | 充值 / 升级订阅 |
| 29003 | 参数错误 | 检查模型与参数组合 |
| 29998 | 触发限流 | 客户端已按文档以 20–30s 指数退避自动重试(免费额度高峰期会被限流) |

所有 API 错误都会附带错误码与处理建议抛出,显示在 ComfyUI 的报错弹窗与日志中。

## License

[Apache-2.0](LICENSE)
