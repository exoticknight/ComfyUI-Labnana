# Changelog

## 2.0.1 - 2026-08-11

- Re-shot the four example-workflow thumbnails to match the 2.0 node layout.
- README install section now points to the Comfy Registry (search "Labnana" in ComfyUI-Manager, or `comfy node registry-install comfyui-labnana`).
- Reworded the package description in usage terms (shown on the registry page).

## 2.0.0 - 2026-08-11

Usage-first repackaging: nodes are now organized around what you want to do, not around API endpoints.

**Breaking changes**

- `Labnana Image Generation` is now the single generation node: it submits an async task, polls and downloads internally (new optional `timeout` input, new outputs `images` / `image_urls` / `task_id`).
- `Labnana Image Generation (Async)` removed — its behavior is what the main node does now. Workflows using it: swap in `Labnana Image Generation`.
- `Labnana Submit Task` / `Get Task` / `List Tasks` moved from the `Labnana/Tasks` category to `Labnana/Advanced`.

**Other**

- Node descriptions rewritten in user terms; the node → endpoint mapping lives in a README appendix.
- README restructured by task (quick start / editing / 4K / cost control / advanced); example workflow `labnana_async_4k` renamed to `labnana_4k`.
- Added a GitHub Action for publishing to the Comfy Registry on `pyproject.toml` changes.

## 1.0.0 - 2026-08-11

Initial release.

- 9 nodes covering the full Labnana OpenAPI surface:
  - Account: `Labnana API Client`, `Labnana Subscription Info`
  - Generate: `Labnana Image Generation` (sync), `Labnana Image Generation (Async)`, `Labnana Estimate Credits`
  - Tasks: `Labnana Submit Task`, `Labnana Get Task`, `Labnana List Tasks`
  - Helpers: `Labnana Load Image From URL`
- Optional `system_prompt` input on all generation nodes (prepended to the prompt; the API has no native system-prompt field).
- Provider auto-derived from model; client-side validation of size/reference-image constraints before spending credits.
- Reference images as inline base64 (auto-downscale/JPEG fallback to fit the 20 MB body limit) and/or `https://`/`gs://` URLs.
- Automatic retry with 20–30 s exponential backoff on rate limiting (code 29998 / HTTP 429).
- API key via node field or `LABNANA_API_KEY` environment variable.
- 4 example workflows with thumbnails in `example_workflows/`, shown in ComfyUI's template browser (text-to-image, image editing, async 4K, account & costs).
