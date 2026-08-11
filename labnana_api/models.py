"""Model registry and request constraints for the Labnana OpenAPI.

Source: https://labnana.com/docs/openapi/guide and
https://docs.marswave.ai/openapi-labnana.html
"""

# model name -> constraints. `provider` is derived automatically so users only
# pick a model in the UI.
MODELS = {
    "gemini-3-pro-image": {
        "provider": "google",
        "image_sizes": ["1K", "2K", "4K"],
        "max_reference_images": 14,
        "credits": {"1K": 15, "2K": 15, "4K": 30},
    },
    "gemini-3.1-flash-image": {
        "provider": "google",
        "image_sizes": ["1K", "2K", "4K"],
        "max_reference_images": 14,
        "credits": {"1K": 10, "2K": 10, "4K": 20},
    },
    "gpt-image-2": {
        "provider": "openai",
        "image_sizes": ["1K", "2K", "4K"],
        "max_reference_images": 4,
        "credits": {"1K": 4, "2K": 6, "4K": 10},
    },
    "wan2.7-image-pro": {
        "provider": "alibaba",
        "image_sizes": ["1K", "2K", "4K"],
        "max_reference_images": 9,
        "credits": {"1K": 6, "2K": 8, "4K": 12},
    },
    "wan2.7-image": {
        "provider": "alibaba",
        "image_sizes": ["1K", "2K"],
        "max_reference_images": 9,
        "credits": {"1K": 4, "2K": 6},
    },
    "seedream-5-0-pro": {
        "provider": "bytedance",
        "image_sizes": ["1K", "2K"],
        "max_reference_images": 10,
        "credits": {"1K": 6, "2K": 15},
    },
}

MODEL_NAMES = list(MODELS.keys())

IMAGE_SIZES = ["1K", "2K", "4K"]

ASPECT_RATIOS = [
    "1:1", "2:3", "3:2", "3:4", "4:3",
    "9:16", "16:9", "21:9",
    "1:4", "4:1", "1:8", "8:1",
]

TASK_STATUSES = ["pending", "generating", "success", "fail"]


def validate_request(model: str, image_size: str, reference_count: int) -> None:
    """Raise ValueError with an actionable message when the combination is
    rejected by the API anyway (fail fast, before spending a network call)."""
    if model not in MODELS:
        raise ValueError(
            f"Unknown Labnana model '{model}'. Available: {', '.join(MODEL_NAMES)}"
        )
    spec = MODELS[model]
    if image_size not in spec["image_sizes"]:
        raise ValueError(
            f"Model '{model}' does not support image size '{image_size}'. "
            f"Supported sizes: {', '.join(spec['image_sizes'])}"
        )
    max_ref = spec["max_reference_images"]
    if reference_count > max_ref:
        raise ValueError(
            f"Model '{model}' accepts at most {max_ref} reference images, "
            f"got {reference_count}. Reduce the batch or switch model."
        )
