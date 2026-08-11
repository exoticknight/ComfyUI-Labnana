"""Conversions between ComfyUI IMAGE tensors, PIL images and the Labnana
request/response formats, plus the shared request-payload builder."""

import base64
import io
import json

import numpy as np
import torch
from PIL import Image

from .models import MODELS, validate_request

# Request bodies are capped at 20 MB; keep inline reference images under a
# conservative per-image budget so multi-image requests still fit.
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


def pil_to_inline_data(img: Image.Image) -> dict:
    """PIL image -> referenceImages inlineData entry (base64 PNG/JPEG)."""
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    if max(img.size) > _MAX_INLINE_SIDE:
        img = img.copy()
        img.thumbnail((_MAX_INLINE_SIDE, _MAX_INLINE_SIDE), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    mime = "image/png"
    if buf.tell() > _INLINE_BUDGET_BYTES:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=92)
        mime = "image/jpeg"
    return {
        "inlineData": {
            "mimeType": mime,
            "data": base64.b64encode(buf.getvalue()).decode("ascii"),
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
    for pil in tensor_batch_to_pils(reference_images):
        refs.append(pil_to_inline_data(pil))

    validate_request(model, image_size, len(refs))

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
