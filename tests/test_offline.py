"""Offline checks for ComfyUI-Labnana: imports the package the way ComfyUI
does, validates node schemas, payload building and response parsing.
No network access or API key required. Run: python tests/test_offline.py
"""

import base64
import importlib
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

pkg = importlib.import_module(ROOT.name)
imaging = importlib.import_module(f"{ROOT.name}.labnana_api.imaging")
models = importlib.import_module(f"{ROOT.name}.labnana_api.models")
client_mod = importlib.import_module(f"{ROOT.name}.labnana_api.client")

import torch
from PIL import Image


def test_node_schemas():
    mappings = pkg.NODE_CLASS_MAPPINGS
    display = pkg.NODE_DISPLAY_NAME_MAPPINGS
    assert set(mappings) == set(display), "mapping keys mismatch"
    for name, cls in mappings.items():
        schema = cls.INPUT_TYPES()
        assert "required" in schema, name
        assert isinstance(cls.RETURN_TYPES, tuple), name
        assert len(cls.RETURN_TYPES) == len(cls.RETURN_NAMES), name
        assert hasattr(cls, cls.FUNCTION), name
        print(f"OK  {name:32s} -> {display[name]}")

    for key in ("LabnanaImageGeneration",
                "LabnanaEstimateCredits", "LabnanaSubmitTask"):
        assert "system_prompt" in mappings[key].INPUT_TYPES()["optional"], key
    print("OK  system_prompt input present on generation nodes")


def test_subscription_outputs():
    class FakeClient:
        @staticmethod
        def get_subscription():
            return {
                "totalAvailableCredits": 12,
                "usageAvailableMonthlyCredits": 5,
                "usageAvailablePermanentCredits": 4,
                "usageAvailableLimitedTimeCredits": 3,
                "paidStatus": True,
                "freeUsages": {
                    "image:test:generation": {"remaining": 2},
                },
            }

    cls = pkg.NODE_CLASS_MAPPINGS["LabnanaSubscription"]
    assert cls.RETURN_NAMES[:5] == (
        "total_credits", "monthly_credits", "permanent_credits",
        "paid_status", "info_json",
    )
    assert cls.RETURN_NAMES[5:] == (
        "limited_time_credits", "free_usages_json",
    )
    result = cls().query(FakeClient())
    assert result[:4] == (12, 5, 4, True)
    assert result[5] == 3
    assert json.loads(result[6])["image:test:generation"]["remaining"] == 2
    print("OK  subscription exposes limited-time credits + free usage")


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
    for bad in [("wan2.7-image", "4K", "1:1", 0),
                ("seedream-5-0-pro", "4K", "1:1", 0),
                ("gpt-image-2", "2K", "1:1", 5),
                ("wan2.7-image", "2K", "2:3", 0),
                ("gemini-3-pro-image", "2K", "1:4", 0),
                ("wan2.7-image-pro", "4K", "1:1", 1)]:
        try:
            models.validate_request(*bad)
            raise AssertionError(f"should have rejected {bad}")
        except ValueError:
            pass
    models.validate_request("gemini-3.1-flash-image", "4K", "1:8", 0)
    models.validate_request("seedream-5-0-pro", "2K", "4:1", 1)
    try:
        imaging.build_payload("gpt-image-2", "  ", "1K", "1:1")
        raise AssertionError("empty prompt accepted")
    except ValueError:
        pass
    print("OK  constraint validation")


def test_inline_request_budget():
    import json

    torch.manual_seed(0)
    images = torch.rand(6, 1024, 1024, 3)
    payload = imaging.build_payload(
        "gemini-3-pro-image", "combine these references", "2K", "1:1",
        reference_images=images,
    )
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    assert len(payload["referenceImages"]) == 6
    assert len(body) <= 20 * 1024 * 1024, len(body)
    print("OK  inline reference images stay within request budget")


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


BUILTIN_NODES = {"Note", "SaveImage", "LoadImage", "PreviewImage"}
CONNECTION_TYPES = {"LABNANA_CLIENT", "IMAGE", "MASK", "LATENT"}


def _expected_widget_count(cls) -> int:
    """Count widget slots the frontend serializes into widgets_values."""
    n = 0
    schema = cls.INPUT_TYPES()
    for section in ("required", "optional"):
        for spec in schema.get(section, {}).values():
            kind, opts = spec[0], (spec[1] if len(spec) > 1 else {})
            if isinstance(kind, list):
                n += 1
            elif kind in ("STRING", "INT", "FLOAT", "BOOLEAN"):
                n += 1
                if opts.get("control_after_generate"):
                    n += 1  # extra "fixed/randomize/..." widget
    return n


def test_example_workflows():
    import json
    wf_dir = ROOT / "example_workflows"
    files = sorted(wf_dir.glob("*.json"))
    assert files, "no example workflows found"
    mappings = pkg.NODE_CLASS_MAPPINGS
    for f in files:
        wf = json.loads(f.read_text(encoding="utf-8"))
        node_ids = {n["id"] for n in wf["nodes"]}
        for n in wf["nodes"]:
            t = n["type"]
            assert t in mappings or t in BUILTIN_NODES, f"{f.name}: {t}"
            if t in mappings:
                want = _expected_widget_count(mappings[t])
                got = len(n.get("widgets_values", []))
                assert got == want, (f"{f.name}: {t} has {got} widget values, "
                                     f"node defines {want}")
        for link_id, src, _s, dst, _d, ltype in wf.get("links", []):
            assert src in node_ids and dst in node_ids, f"{f.name}: link {link_id}"
            assert ltype in CONNECTION_TYPES.union({"STRING", "INT"}), ltype
        assert f.with_suffix(".jpg").exists(), f"{f.name}: missing thumbnail"
        print(f"OK  workflow {f.name}")


def test_client():
    saved = os.environ.pop("LABNANA_API_KEY", None)
    saved_custom_url = os.environ.pop("LABNANA_ALLOW_CUSTOM_BASE_URL", None)
    try:
        try:
            client_mod.LabnanaClient(api_key="")
            raise AssertionError("empty key accepted")
        except client_mod.LabnanaError as e:
            assert "labnana.com/api-keys" in str(e)
        c = client_mod.LabnanaClient(api_key="ls_test")
        assert c._session.headers["Authorization"] == "Bearer ls_test"
        assert c._session.headers["User-Agent"] == (
            f"ComfyUI-Labnana/{client_mod.CLIENT_VERSION}"
        )
        version_line = next(
            line for line in (ROOT / "pyproject.toml").read_text().splitlines()
            if line.startswith("version = ")
        )
        assert client_mod.CLIENT_VERSION == version_line.split('"')[1]
        try:
            client_mod.LabnanaClient(
                api_key="ls_test", base_url="https://example.com")
            raise AssertionError("unapproved custom base URL accepted")
        except client_mod.LabnanaError as e:
            assert "LABNANA_ALLOW_CUSTOM_BASE_URL" in str(e)
        os.environ["LABNANA_ALLOW_CUSTOM_BASE_URL"] = "1"
        custom = client_mod.LabnanaClient(
            api_key="ls_test", base_url="https://staging.example.com/")
        assert custom.base_url == "https://staging.example.com"
    finally:
        if saved is not None:
            os.environ["LABNANA_API_KEY"] = saved
        if saved_custom_url is None:
            os.environ.pop("LABNANA_ALLOW_CUSTOM_BASE_URL", None)
        else:
            os.environ["LABNANA_ALLOW_CUSTOM_BASE_URL"] = saved_custom_url
    print("OK  client auth + missing-key error")


if __name__ == "__main__":
    test_node_schemas()
    test_subscription_outputs()
    test_payload_building()
    test_validation()
    test_inline_request_budget()
    test_sync_response_parsing()
    test_example_workflows()
    test_client()
    print("\nALL CHECKS PASSED")
