# Changelog

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
