"""Conversions between ComfyUI IMAGE tensors, PIL images and the Labnana
request/response formats, plus the shared request-payload builder."""

import base64
import io
import json
import math

import numpy as np
import torch
from PIL import Image

from .models import MODELS, validate_request

# Request bodies are capped at 20 MB. Reserve space for JSON structure, URLs,
# and prompts, then share the remaining encoded-data budget across all inline
# images in the request.
_MAX_REQUEST_BYTES = 20 * 1024 * 1024
_INLINE_TOTAL_BUDGET_BYTES = 18 * 1024 * 1024
_INLINE_BUDGET_BYTES = 6 * 1024 * 1024
_MAX_INLINE_SIDE = 3072


def tensor_batch_to_pils(images: torch.Tensor):
    """ComfyUI IMAGE tensor [B,H,W,C] float 0-1 -> list of PIL images."""
    if images is None:
        return []
    pils = []
    for i in range(images.shape[0]):
        arr = images[i].detach().cpu().numpy()
        arr = np.clip(arr * 255.0 + 0.5, 0, 255).astype(np.uint8)
        pils.append(Image.fromarray(arr))
    return pils


def pil_to_inline_data(img: Image.Image,
                       max_encoded_bytes: int = _INLINE_BUDGET_BYTES) -> dict:
    """PIL image -> referenceImages inlineData entry (base64 PNG/JPEG)."""
    if max_encoded_bytes <= 0:
        raise ValueError("No request-body budget remains for reference images")
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    if max(img.size) > _MAX_INLINE_SIDE:
        img = img.copy()
        img.thumbnail((_MAX_INLINE_SIDE, _MAX_INLINE_SIDE), Image.LANCZOS)

    def encode(candidate, image_format, **save_kwargs):
        buf = io.BytesIO()
        candidate.save(buf, format=image_format, **save_kwargs)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    encoded = encode(img, "PNG")
    mime = "image/png"
    if len(encoded) > max_encoded_bytes:
        candidate = img.convert("RGB")
        while True:
            for quality in (92, 82, 72, 60, 48):
                encoded = encode(candidate, "JPEG", quality=quality,
                                 optimize=True)
                if len(encoded) <= max_encoded_bytes:
                    mime = "image/jpeg"
                    break
            else:
                scale = math.sqrt(max_encoded_bytes / len(encoded)) * 0.9
                new_size = (
                    max(64, int(candidate.width * scale)),
                    max(64, int(candidate.height * scale)),
                )
                if new_size == candidate.size:
                    raise ValueError(
                        "Reference image cannot fit within the 20 MB request "
                        "body limit"
                    )
                candidate = candidate.resize(new_size, Image.LANCZOS)
                continue
            break
    return {
        "inlineData": {
            "mimeType": mime,
            "data": encoded,
        }
    }


def url_to_file_data(url: str) -> dict:
    """URL string -> referenceImages fileData entry."""
    url = url.strip()
    lower = url.lower()
    if lower.endswith((".jpg", ".jpeg")):
        mime = "image/jpeg"
    elif lower.endswith(".webp"):
        mime = "image/webp"
    else:
        mime = "image/png"
    return {"fileData": {"fileUri": url, "mimeType": mime}}


def pils_to_image_batch(pils) -> torch.Tensor:
    """PIL images -> ComfyUI IMAGE tensor [B,H,W,C]; resizes any stragglers to
    the first image's dimensions so they can share one batch."""
    if not pils:
        raise ValueError("No images to convert")
    first = pils[0].convert("RGB")
    w, h = first.size
    arrays = []
    for img in pils:
        img = img.convert("RGB")
        if img.size != (w, h):
            img = img.resize((w, h), Image.LANCZOS)
        arrays.append(np.asarray(img).astype(np.float32) / 255.0)
    return torch.from_numpy(np.stack(arrays, axis=0))


def bytes_to_pil(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def build_payload(model: str, prompt: str, image_size: str, aspect_ratio: str,
                  reference_images: torch.Tensor = None,
                  reference_image_urls: str = "",
                  system_prompt: str = "") -> dict:
    """Build the request body shared by generate / generate_async / estimate.

    The API has no native system-prompt field, so a non-empty `system_prompt`
    is prepended to the prompt (separated by a blank line)."""
    prompt = (prompt or "").strip()
    system_prompt = (system_prompt or "").strip()
    if system_prompt:
        prompt = f"{system_prompt}\n\n{prompt}" if prompt else system_prompt
    if not prompt:
        raise ValueError("prompt is empty")

    refs = []
    for url in (reference_image_urls or "").replace(",", "\n").splitlines():
        if url.strip():
            refs.append(url_to_file_data(url))
    pils = tensor_batch_to_pils(reference_images)
    remaining_budget = _INLINE_TOTAL_BUDGET_BYTES
    for index, pil in enumerate(pils):
        remaining_images = len(pils) - index
        image_budget = remaining_budget // remaining_images
        inline = pil_to_inline_data(pil, max_encoded_bytes=image_budget)
        remaining_budget -= len(inline["inlineData"]["data"])
        refs.append(inline)

    validate_request(model, image_size, aspect_ratio, len(refs))

    payload = {
        "provider": MODELS[model]["provider"],
        "model": model,
        "prompt": prompt,
        "imageConfig": {
            "imageSize": image_size,
            "aspectRatio": aspect_ratio,
        },
    }
    if refs:
        payload["referenceImages"] = refs
    body_size = len(json.dumps(payload).encode("utf-8"))
    if body_size > _MAX_REQUEST_BYTES:
        raise ValueError(
            f"Generation request is {body_size / 1024 / 1024:.1f} MB; "
            "the Labnana API limit is 20 MB. Shorten the prompt/URLs or "
            "reduce the number of reference images."
        )
    return payload


def parse_sync_response(resp: dict):
    """Gemini-style sync response -> (list[PIL], response_text).

    Raises with diagnostics (finishReason / safety ratings / text parts) when
    no image came back, so the user sees *why* instead of a KeyError."""
    pils, texts = [], []
    candidates = resp.get("candidates") or []
    for cand in candidates:
        parts = ((cand.get("content") or {}).get("parts")) or []
        for part in parts:
            inline = part.get("inlineData")
            if inline and inline.get("data"):
                pils.append(bytes_to_pil(base64.b64decode(inline["data"])))
            elif part.get("text"):
                texts.append(part["text"])

    if not pils:
        details = {
            "finishReason": (candidates[0].get("finishReason")
                             if candidates else None),
            "safetyRatings": (candidates[0].get("safetyRatings")
                              if candidates else None),
            "promptFeedback": resp.get("promptFeedback"),
            "text": " ".join(texts) or None,
            "message": resp.get("message"),
        }
        details = {k: v for k, v in details.items() if v}
        raise RuntimeError(
            "Labnana returned no image. Details: "
            + json.dumps(details, ensure_ascii=False, default=str))

    return pils, "\n".join(texts)
