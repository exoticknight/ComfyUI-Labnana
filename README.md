# ComfyUI-Labnana

[![CI](https://github.com/exoticknight/ComfyUI-Labnana/actions/workflows/ci.yml/badge.svg)](https://github.com/exoticknight/ComfyUI-Labnana/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/exoticknight/ComfyUI-Labnana)](https://github.com/exoticknight/ComfyUI-Labnana/releases)
[![Comfy Registry](https://img.shields.io/badge/Comfy_Registry-comfyui--labnana-1a56db)](https://registry.comfy.org/publishers/exoticknight/nodes/comfyui-labnana)
[![License](https://img.shields.io/github/license/exoticknight/ComfyUI-Labnana)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](pyproject.toml)

[中文文档](README.zh-CN.md) | English

ComfyUI custom nodes for the [Labnana](https://labnana.com) (Marswave) image generation API. One generation node covers text-to-image, image editing and 4K output — submission, waiting and download all happen inside the node. Cost-control and task-history tools included.

- Integration guide: <https://labnana.com/docs/openapi/guide>
- Full API reference: <https://docs.marswave.ai/openapi-labnana.html>

## Installation

**Via ComfyUI-Manager** (recommended): open **Manager → Custom Nodes Manager**, search for **Labnana** and install. Also available on the [Comfy Registry](https://registry.comfy.org/publishers/exoticknight/nodes/comfyui-labnana):

```
comfy node registry-install comfyui-labnana
```

**Manual**:

```
cd ComfyUI/custom_nodes
git clone https://github.com/exoticknight/ComfyUI-Labnana.git
```

Restart ComfyUI. The only dependency is `requests`, which ships with ComfyUI. Nodes appear under the **Labnana** category.

## API key

Create a key (starts with `ls_`) at <https://labnana.com/api-keys>, then either:

1. paste it into the `api_key` field of the **Labnana API Client** node, or
2. set the `LABNANA_API_KEY` environment variable and leave the field empty — recommended, so the key never leaks into shared workflow JSON files.

## Quick start: text to image

`Labnana API Client` → `Labnana Image Generation` → `Save Image`. Type a prompt, pick a `model`, `image_size` and `aspect_ratio`, press Run. The node handles everything else internally.

- The `provider` is derived from the model automatically.
- `image_urls` also outputs the public result URLs (valid 7 days).
- The `seed` widget is never sent to the API — it only forces ComfyUI to re-execute the node instead of serving the cached result. Set it to *randomize* to regenerate every run.

## Editing images (img2img)

Connect a `Load Image` node to `reference_images` and write the editing instructions in the prompt. Reference images can come from two inputs, freely combined, subject to the per-model cap (4–14):

- `reference_images` (IMAGE): a ComfyUI image batch, uploaded inline as base64 (auto-downscaled to ≤3072 px / JPEG fallback to stay under the 20 MB body limit);
- `reference_image_urls` (STRING): one `https://` or `gs://` URL per line.

**Style presets**: every generation node accepts an optional `system_prompt`, prepended to the prompt (the API has no native system-prompt field) — handy for sharing one style/behavior preamble across workflows.

## 4K and slow jobs

Nothing special to wire — pick `4K` as the image size. If a job needs longer than the default 10-minute wait, raise the node's optional `timeout` input.

## Controlling costs

- **Labnana Estimate Credits** takes the same inputs as the generation node and returns `credits` and `can_generate` — check the price before spending.
- **Labnana Subscription Info** shows your credit balances and plan status.
- Invalid combinations (e.g. 4K on wan2.7-image, too many reference images) fail fast locally before any credits are spent.

## Models and constraints

| Model | Provider | Sizes | Max ref images | Credits (1K/2K/4K) |
|---|---|---|---|---|
| gemini-3-pro-image | google | 1K/2K/4K | 14 | 15/15/30 |
| gemini-3.1-flash-image | google | 1K/2K/4K | 14 | 10/10/20 |
| gpt-image-2 | openai | 1K/2K/4K | 4 | 4/6/10 |
| wan2.7-image-pro | alibaba | 1K/2K/4K | 9 | 6/8/12 |
| wan2.7-image | alibaba | 1K/2K | 9 | 4/6 |
| seedream-5-0-pro | bytedance | 1K/2K | 10 | 6/15 |

Aspect ratios: `1:1, 2:3, 3:2, 3:4, 4:3, 9:16, 16:9, 21:9, 1:4, 4:1, 1:8, 8:1`.

Credit prices follow the [official docs](https://docs.marswave.ai/openapi-labnana.html) and may change — the **Estimate Credits** node always returns the live cost.

## Advanced: task management

For batch pipelines and fire-and-forget jobs, the async task API is exposed under **Labnana/Advanced**:

- **Labnana Submit Task** — submit only, returns a `task_id` immediately without waiting;
- **Labnana Get Task** — fetch (or wait for) a task by `task_id` any time later and download its images;
- **Labnana List Tasks** — paged generation history with status filter;
- **Labnana Load Image From URL** — turn result URLs (or any image URL) back into an IMAGE batch.

For normal use you never need these — `Labnana Image Generation` does submit + wait + download in one node.

## Example workflows

Ready-made workflows ship in [example_workflows/](example_workflows) and appear in ComfyUI under **Workflow → Browse Templates → ComfyUI-Labnana** (you can also drag the JSON files onto the canvas):

| ![Text to Image](example_workflows/labnana_text_to_image.jpg) | ![Image Editing](example_workflows/labnana_image_editing.jpg) |
|:---:|:---:|
| **Text to Image** — minimal generation | **Image Editing** — reference image + `system_prompt` guardrails |
| ![4K Generation](example_workflows/labnana_4k.jpg) | ![Account & Costs](example_workflows/labnana_account_and_costs.jpg) |
| **4K Generation** — high-res with a longer timeout | **Account & Costs** — balance, credit estimate and task history before spending credits |

## Error handling

| Code | Meaning | Action |
|---|---|---|
| 21007 | Invalid API key | Check the key configuration |
| 26004 | Insufficient credits | Top up / upgrade the plan |
| 29003 | Parameter error | Check the model/parameter combination |
| 29998 | Rate limited | The client already retries with the documented 20–30 s exponential backoff |

All API errors are raised with the error code and a remediation hint, visible in the ComfyUI error dialog and log.

## Development

Offline tests (no API key or network needed, requires torch/Pillow/numpy):

```
python tests/test_offline.py
```

<details>
<summary><b>Node → API endpoint mapping</b></summary>

| Node | Endpoint |
|---|---|
| Labnana Subscription Info | `GET /openapi/v1/user/subscription` |
| Labnana Image Generation | `POST /openapi/v1/images/generation/async` + `GET .../tasks/{taskId}` polling |
| Labnana Estimate Credits | `POST /openapi/v1/images/generation/estimate-credits` |
| Labnana Submit Task | `POST /openapi/v1/images/generation/async` |
| Labnana Get Task | `GET /openapi/v1/images/generation/tasks/{taskId}` |
| Labnana List Tasks | `GET /openapi/v1/images/generation/tasks` |

The synchronous endpoint (`POST /openapi/v1/images/generation`) is implemented in the bundled `labnana_api` client library but not exposed as a node — the async flow is more robust for every size.

</details>

## License

[Apache-2.0](LICENSE)
