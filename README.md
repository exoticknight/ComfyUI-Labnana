# ComfyUI-Labnana

[中文文档](README.zh-CN.md) | English

ComfyUI custom nodes for the [Labnana](https://labnana.com) (Marswave) image generation OpenAPI. Full coverage of the official API surface: synchronous generation, async tasks (submit / poll / history), credit estimation and subscription info.

- Integration guide: <https://labnana.com/docs/openapi/guide>
- Full API reference: <https://docs.marswave.ai/openapi-labnana.html>

## Installation

```
cd ComfyUI/custom_nodes
git clone https://github.com/exoticknight/ComfyUI-Labnana.git
```

Restart ComfyUI. The only dependency is `requests`, which ships with ComfyUI. Nodes appear under the **Labnana** category.

## API key

Create a key (starts with `ls_`) at <https://labnana.com/api-keys>, then either:

1. paste it into the `api_key` field of the **Labnana API Client** node, or
2. set the `LABNANA_API_KEY` environment variable and leave the field empty — recommended, so the key never leaks into shared workflow JSON files.

## Nodes

| Node | Category | Endpoint | Purpose |
|---|---|---|---|
| Labnana API Client | Account | — | Configure key/timeout/retries; outputs a reusable `client` |
| Labnana Subscription Info | Account | `GET /user/subscription` | Credit balances and plan status |
| Labnana Image Generation | Generate | `POST /images/generation` | Synchronous, image returned directly (base64) |
| Labnana Image Generation (Async) | Generate | `POST /images/generation/async` + polling | Auto-polls and downloads result URLs; robust for 4K/slow jobs |
| Labnana Estimate Credits | Generate | `POST /images/generation/estimate-credits` | Cost and feasibility check before generating |
| Labnana Submit Task | Tasks | `POST /images/generation/async` | Submit only, returns taskId immediately |
| Labnana Get Task | Tasks | `GET /images/generation/tasks/{taskId}` | Fetch/wait for a task and download its images |
| Labnana List Tasks | Tasks | `GET /images/generation/tasks` | Paged task history with status filter |
| Labnana Load Image From URL | Helpers | — | Load result URLs (or any image URL) as an IMAGE batch |

## Models and constraints

You only pick a `model`; the `provider` is derived automatically:

| Model | Provider | Sizes | Max ref images | Credits (1K/2K/4K) |
|---|---|---|---|---|
| gemini-3-pro-image | google | 1K/2K/4K | 14 | 15/15/30 |
| gemini-3.1-flash-image | google | 1K/2K/4K | 14 | 10/10/20 |
| gpt-image-2 | openai | 1K/2K/4K | 4 | 4/6/10 |
| wan2.7-image-pro | alibaba | 1K/2K/4K | 9 | 6/8/12 |
| wan2.7-image | alibaba | 1K/2K | 9 | 4/6 |
| seedream-5-0-pro | bytedance | 1K/2K | 10 | 6/15 |

Aspect ratios: `1:1, 2:3, 3:2, 3:4, 4:3, 9:16, 16:9, 21:9, 1:4, 4:1, 1:8, 8:1`.

Invalid combinations (e.g. 4K on wan2.7-image, too many reference images) fail fast locally before any credits are spent.

## Reference images (img2img / editing)

Two inputs, freely combined, subject to the per-model cap:

- `reference_images` (IMAGE): a ComfyUI image batch, uploaded inline as base64 (auto-downscaled to ≤3072 px / JPEG fallback to stay under the 20 MB body limit);
- `reference_image_urls` (STRING): one `https://` or `gs://` URL per line, sent as fileData references.

## System prompt

All four generation-payload nodes accept an optional `system_prompt`. The API has no native system-prompt field, so it is prepended to the prompt (blank-line separated) — handy for sharing one style/behavior preamble across workflows.

## Example workflows

Ready-made workflows ship in [example_workflows/](example_workflows) and appear in ComfyUI under **Workflow → Browse Templates → ComfyUI-Labnana** (you can also drag the JSON files onto the canvas):

- **Text to Image** — minimal synchronous generation
- **Image Editing** — reference image + `system_prompt` guardrails
- **Async 4K Generation** — submit / poll / download for slow jobs
- **Account & Costs** — balance, credit estimate and task history before spending credits

## Typical wiring

- **Text-to-image**: `Labnana API Client` → `Labnana Image Generation` → `Save Image`.
- **Editing**: same, with `Load Image` connected to `reference_images` and editing instructions in the prompt.
- **Long-running jobs**: `Labnana Submit Task` → keep the `task_id` → fetch later with `Labnana Get Task` (or use the one-step Async node).
- **Cost control**: check `credits` / `can_generate` from `Labnana Estimate Credits` first.

The `seed` widget is never sent to the API — it only forces ComfyUI to re-execute the node instead of serving the cached result. Set it to *randomize* to regenerate every run.

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

## License

[Apache-2.0](LICENSE)
