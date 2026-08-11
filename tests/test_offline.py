"""Offline checks for ComfyUI-Labnana: imports the package the way ComfyUI
does, validates node schemas, payload building and response parsing.
No network access or API key required. Run: python tests/test_offline.py
"""

import base64
import importlib
import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

pkg = importlib.import_module(ROOT.name)
imaging = importlib.import_module(f"{ROOT.name}.labnana_api.imaging")
models = importlib.import_module(f"{ROOT.name}.labnana_api.models")
client_mod = importlib.import_module(f"{ROOT.name}.labnana_api.client")

import torch  # noqa: E402  (after sys.path setup on purpose)
from PIL import Image  # noqa: E402


def test_node_schemas():
    mappings = pkg.NODE_CLASS_MAPPINGS
    display = pkg.NODE_DISPLAY_NAME_MAPPINGS
    assert set(mappings) == set(display), "mapping keys mismatch"
    for name, cls in mappings.items():
        schema = cls.INPUT_TYPES()
        assert "required" in schema, name
        assert isinstance(cls.RETURN_TYPES, tuple), name
        assert len(cls.RETURN_TYPES) == len(cls.RETURN_NAMES), name
        assert hasattr(cls, getattr(cls, "FUNCTION")), name
        print(f"OK  {name:32s} -> {display[name]}")

    for key in ("LabnanaImageGeneration", "LabnanaImageGenerationAsync",
                "LabnanaEstimateCredits", "LabnanaSubmitTask"):
        assert "system_prompt" in mappings[key].INPUT_TYPES()["optional"], key
    print("OK  system_prompt input present on generation nodes")


def test_payload_building():
    img = torch.rand(2, 64, 64, 3)
    p = imaging.build_payload("gemini-3-pro-image", "a cat", "2K", "16:9",
                              reference_images=img,
                              reference_image_urls="https://x.com/a.jpg")
    assert p["provider"] == "google"
    assert len(p["referenceImages"]) == 3
    assert p["referenceImages"][0]["fileData"]["mimeType"] == "image/jpeg"
    assert "inlineData" in p["referenceImages"][1]
    assert p["imageConfig"] == {"imageSize": "2K", "aspectRatio": "16:9"}

    p2 = imaging.build_payload("gpt-image-2", "a cat", "1K", "1:1",
                               system_prompt="Use watercolor style.")
    assert p2["prompt"] == "Use watercolor style.\n\na cat"
    p3 = imaging.build_payload("gpt-image-2", "", "1K", "1:1",
                               system_prompt="only system")
    assert p3["prompt"] == "only system"
    print("OK  payload building + system prompt")


def test_validation():
    for bad in [("wan2.7-image", "4K", 0), ("seedream-5-0-pro", "4K", 0),
                ("gpt-image-2", "2K", 5)]:
        try:
            models.validate_request(*bad)
            raise AssertionError(f"should have rejected {bad}")
        except ValueError:
            pass
    try:
        imaging.build_payload("gpt-image-2", "  ", "1K", "1:1")
        raise AssertionError("empty prompt accepted")
    except ValueError:
        pass
    print("OK  constraint validation")


def test_sync_response_parsing():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buf, format="PNG")
    resp = {"candidates": [{"content": {"role": "model", "parts": [
        {"inlineData": {"mimeType": "image/png",
                        "data": base64.b64encode(buf.getvalue()).decode()}},
        {"text": "done"}]}, "finishReason": "STOP"}]}
    pils, text = imaging.parse_sync_response(resp)
    batch = imaging.pils_to_image_batch(pils)
    assert batch.shape == (1, 8, 8, 3) and text == "done"

    try:
        imaging.parse_sync_response({"candidates": [{"content": {"parts": [
            {"text": "blocked"}]}, "finishReason": "SAFETY"}]})
        raise AssertionError("no-image response accepted")
    except RuntimeError as e:
        assert "SAFETY" in str(e)
    print("OK  sync response parsing + no-image diagnostics")


def test_client():
    saved = os.environ.pop("LABNANA_API_KEY", None)
    try:
        try:
            client_mod.LabnanaClient(api_key="")
            raise AssertionError("empty key accepted")
        except client_mod.LabnanaError as e:
            assert "labnana.com/api-keys" in str(e)
        c = client_mod.LabnanaClient(api_key="ls_test")
        assert c._session.headers["Authorization"] == "Bearer ls_test"
    finally:
        if saved is not None:
            os.environ["LABNANA_API_KEY"] = saved
    print("OK  client auth + missing-key error")


if __name__ == "__main__":
    test_node_schemas()
    test_payload_building()
    test_validation()
    test_sync_response_parsing()
    test_client()
    print("\nALL CHECKS PASSED")
