"""Opt-in live smoke test for the GPT-Image-2.5 model variants.

Run without --generate to request free estimates only. Add --generate to
submit one 1K image for each model after both estimates report that generation
is available. Requires LABNANA_API_KEY in the local environment.
"""

import argparse
import importlib
import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

imaging = importlib.import_module(f"{ROOT.name}.labnana_api.imaging")
client_mod = importlib.import_module(f"{ROOT.name}.labnana_api.client")

MODELS = ("gpt-image-2.5-flare", "gpt-image-2.5-sunburst")
PROMPT = "A small cobalt-blue glass vase on a white studio surface, soft natural light."


def _inspect_image(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        return image.size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generate",
        action="store_true",
        help="generate one 1K image with each model after estimating both",
    )
    args = parser.parse_args()

    try:
        client = client_mod.LabnanaClient()
    except client_mod.LabnanaError as exc:
        parser.error(str(exc))

    payloads = {
        model: imaging.build_payload(model, PROMPT, "1K", "1:1")
        for model in MODELS
    }
    estimates = {}
    for model, payload in payloads.items():
        estimate = client.estimate_credits(payload)
        credits = estimate.get("credits")
        can_generate = estimate.get("canGenerate")
        if not isinstance(credits, int) or not isinstance(can_generate, bool):
            raise TypeError(f"Unexpected estimate response for {model}")
        estimates[model] = (credits, can_generate)
        print(f"{model}: {credits} credits; canGenerate={can_generate}")
        for warning in estimate.get("warnings") or []:
            print(f"  warning: {warning}")

    if not args.generate:
        print("Estimate-only run complete; no generation was submitted.")
        return 0

    unavailable = [model for model, (_, can_generate) in estimates.items()
                   if not can_generate]
    if unavailable:
        print("Generation skipped; estimates are unavailable for: "
              + ", ".join(unavailable))
        return 1

    total = sum(credits for credits, _ in estimates.values())
    print(f"Submitting two 1K images; estimated total: {total} credits.")
    for model, payload in payloads.items():
        submitted = client.generate_async(payload)
        task_id = submitted.get("taskId")
        if not task_id:
            raise RuntimeError(f"{model}: API returned no taskId")
        print(f"{model}: submitted task {task_id}")
        task = client.wait_for_task(task_id, poll_interval=5.0, timeout=600.0)
        images = task.get("images") or []
        urls = [image.get("url") for image in images if image.get("url")]
        if not urls:
            raise RuntimeError(f"{model}: task completed without image URLs")
        for index, url in enumerate(urls, start=1):
            size = _inspect_image(client.download(url))
            print(f"{model}: image {index} downloaded and decoded ({size[0]}×{size[1]})")

    print("Both GPT-Image-2.5 variants generated and returned decodable images.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
