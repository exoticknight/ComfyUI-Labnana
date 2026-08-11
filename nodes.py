"""ComfyUI node definitions for the Labnana OpenAPI.

Nodes:
  Account   : Labnana API Client, Labnana Subscription
  Generate  : Labnana Image Generation (sync),
              Labnana Image Generation (Async) (submit + wait + download),
              Labnana Estimate Credits
  Tasks     : Labnana Submit Task, Labnana Get Task, Labnana List Tasks
  Helpers   : Labnana Load Image From URL
"""

import json

from .labnana_api import (
    LabnanaClient, LabnanaError, DEFAULT_BASE_URL, API_KEY_ENV,
    MODEL_NAMES, ASPECT_RATIOS, IMAGE_SIZES, TASK_STATUSES,
)
from .labnana_api.imaging import (
    build_payload, parse_sync_response, pils_to_image_batch, bytes_to_pil,
)

CATEGORY_ROOT = "Labnana"


def _pretty(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _generation_inputs(extra_required=None, extra_optional=None):
    """Shared INPUT_TYPES for every node that builds a generation payload."""
    required = {
        "client": ("LABNANA_CLIENT",),
        "prompt": ("STRING", {
            "multiline": True, "default": "",
            "tooltip": "Generation or editing instructions."}),
        "model": (MODEL_NAMES, {"default": MODEL_NAMES[0]}),
        "image_size": (IMAGE_SIZES, {
            "default": "2K",
            "tooltip": "4K unsupported on wan2.7-image / seedream-5-0-pro."}),
        "aspect_ratio": (ASPECT_RATIOS, {"default": "1:1"}),
    }
    required.update(extra_required or {})
    optional = {
        "system_prompt": ("STRING", {
            "multiline": True, "default": "",
            "tooltip": "Optional style/behavior instructions prepended to the "
                       "prompt (the API has no native system-prompt field)."}),
        "reference_images": ("IMAGE", {
            "tooltip": "Batch of reference images, sent inline as base64. "
                       "Max count depends on model (4-14)."}),
        "reference_image_urls": ("STRING", {
            "multiline": True, "default": "",
            "tooltip": "Optional http(s):// or gs:// image URLs, "
                       "one per line, sent as fileData references."}),
    }
    optional.update(extra_optional or {})
    return {"required": required, "optional": optional}


# --------------------------------------------------------------------- client


class LabnanaClientNode:
    """Create a reusable API client. Feed it into every other Labnana node."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {
                    "default": "",
                    "tooltip": f"Labnana API key (ls_...). Leave empty to use "
                               f"the {API_KEY_ENV} environment variable. "
                               "Create keys at https://labnana.com/api-keys"}),
            },
            "optional": {
                "base_url": ("STRING", {"default": DEFAULT_BASE_URL}),
                "timeout": ("INT", {"default": 300, "min": 10, "max": 3600,
                                    "tooltip": "Per-request timeout (seconds)."}),
                "max_retries": ("INT", {"default": 3, "min": 0, "max": 10,
                                        "tooltip": "Retries on rate limiting "
                                                   "(20-30s backoff)."}),
            },
        }

    RETURN_TYPES = ("LABNANA_CLIENT",)
    RETURN_NAMES = ("client",)
    FUNCTION = "create"
    CATEGORY = f"{CATEGORY_ROOT}/Account"
    DESCRIPTION = "Configures the Labnana OpenAPI connection (auth, timeouts)."

    def create(self, api_key, base_url=DEFAULT_BASE_URL, timeout=300,
               max_retries=3):
        client = LabnanaClient(api_key=api_key, base_url=base_url,
                               timeout=timeout, max_retries=max_retries)
        return (client,)


class LabnanaSubscriptionNode:
    """Query credit balances and subscription status."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"client": ("LABNANA_CLIENT",)}}

    RETURN_TYPES = ("INT", "INT", "INT", "BOOLEAN", "STRING")
    RETURN_NAMES = ("total_credits", "monthly_credits", "permanent_credits",
                    "paid_status", "info_json")
    FUNCTION = "query"
    CATEGORY = f"{CATEGORY_ROOT}/Account"
    OUTPUT_NODE = True
    DESCRIPTION = "GET /openapi/v1/user/subscription — credit balances and plan."

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")  # balances change server-side; always re-query

    def query(self, client):
        data = client.get_subscription()
        info = _pretty(data)
        print(f"[Labnana] subscription:\n{info}")
        return (
            int(data.get("totalAvailableCredits", 0)),
            int(data.get("usageAvailableMonthlyCredits", 0)),
            int(data.get("usageAvailablePermanentCredits", 0)),
            bool(data.get("paidStatus", False)),
            info,
        )


# ----------------------------------------------------------------- generation


class LabnanaImageGenerationNode:
    """Synchronous generation: request -> base64 image(s) in the response."""

    @classmethod
    def INPUT_TYPES(cls):
        return _generation_inputs(extra_required={
            "seed": ("INT", {
                "default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF,
                "control_after_generate": True,
                "tooltip": "Not sent to the API — changes force ComfyUI to "
                           "re-run the node instead of using the cached "
                           "result."}),
        })

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "response_text")
    FUNCTION = "generate"
    CATEGORY = f"{CATEGORY_ROOT}/Generate"
    DESCRIPTION = ("POST /openapi/v1/images/generation — synchronous, returns "
                   "the image directly (base64). Best for interactive use.")

    def generate(self, client, prompt, model, image_size, aspect_ratio, seed,
                 system_prompt="", reference_images=None,
                 reference_image_urls=""):
        payload = build_payload(model, prompt, image_size, aspect_ratio,
                                reference_images, reference_image_urls,
                                system_prompt)
        resp = client.generate(payload)
        pils, text = parse_sync_response(resp)
        return (pils_to_image_batch(pils), text)


class LabnanaImageGenerationAsyncNode:
    """Submit an async task, poll until done, download the result URLs."""

    @classmethod
    def INPUT_TYPES(cls):
        return _generation_inputs(extra_required={
            "seed": ("INT", {
                "default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF,
                "control_after_generate": True,
                "tooltip": "Not sent to the API — cache-busting only."}),
            "poll_interval": ("FLOAT", {"default": 5.0, "min": 1.0,
                                        "max": 60.0, "step": 0.5}),
            "timeout": ("FLOAT", {"default": 600.0, "min": 30.0,
                                  "max": 3600.0, "step": 10.0,
                                  "tooltip": "Max seconds to wait for the "
                                             "task to finish."}),
        })

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("images", "image_urls", "task_id")
    FUNCTION = "generate"
    CATEGORY = f"{CATEGORY_ROOT}/Generate"
    DESCRIPTION = ("POST /openapi/v1/images/generation/async + polling — "
                   "returns public image URLs; more robust for 4K/slow jobs.")

    def generate(self, client, prompt, model, image_size, aspect_ratio, seed,
                 poll_interval, timeout, system_prompt="",
                 reference_images=None, reference_image_urls=""):
        payload = build_payload(model, prompt, image_size, aspect_ratio,
                                reference_images, reference_image_urls,
                                system_prompt)
        submitted = client.generate_async(payload)
        task_id = submitted.get("taskId", "")
        print(f"[Labnana] async task submitted: {task_id}")

        def progress(status, _task):
            print(f"[Labnana] task {task_id}: {status}")

        task = client.wait_for_task(task_id, poll_interval=poll_interval,
                                    timeout=timeout, progress_cb=progress)
        images = task.get("images") or []
        if not images:
            raise LabnanaError(f"Task {task_id} succeeded but returned no images")
        urls = [img["url"] for img in images if img.get("url")]
        pils = [bytes_to_pil(client.download(u)) for u in urls]
        return (pils_to_image_batch(pils), "\n".join(urls), task_id)


class LabnanaEstimateCreditsNode:
    """Dry-run cost check before generating."""

    @classmethod
    def INPUT_TYPES(cls):
        return _generation_inputs()

    RETURN_TYPES = ("INT", "BOOLEAN", "STRING")
    RETURN_NAMES = ("credits", "can_generate", "info_json")
    FUNCTION = "estimate"
    CATEGORY = f"{CATEGORY_ROOT}/Generate"
    OUTPUT_NODE = True
    DESCRIPTION = ("POST /openapi/v1/images/generation/estimate-credits — "
                   "cost and feasibility without generating.")

    def estimate(self, client, prompt, model, image_size, aspect_ratio,
                 system_prompt="", reference_images=None,
                 reference_image_urls=""):
        payload = build_payload(model, prompt, image_size, aspect_ratio,
                                reference_images, reference_image_urls,
                                system_prompt)
        data = client.estimate_credits(payload)
        info = _pretty(data)
        print(f"[Labnana] estimate:\n{info}")
        warnings = data.get("warnings") or []
        for w in warnings:
            print(f"[Labnana] warning: {w}")
        return (int(data.get("credits", 0)),
                bool(data.get("canGenerate", False)), info)


# ---------------------------------------------------------------------- tasks


class LabnanaSubmitTaskNode:
    """Fire-and-forget async submission; pair with 'Labnana Get Task'."""

    @classmethod
    def INPUT_TYPES(cls):
        return _generation_inputs(extra_required={
            "seed": ("INT", {
                "default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF,
                "control_after_generate": True,
                "tooltip": "Not sent to the API — cache-busting only."}),
        })

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("task_id", "status")
    FUNCTION = "submit"
    CATEGORY = f"{CATEGORY_ROOT}/Tasks"
    OUTPUT_NODE = True
    DESCRIPTION = ("POST /openapi/v1/images/generation/async — submit only, "
                   "returns immediately with a taskId.")

    def submit(self, client, prompt, model, image_size, aspect_ratio, seed,
               system_prompt="", reference_images=None,
               reference_image_urls=""):
        payload = build_payload(model, prompt, image_size, aspect_ratio,
                                reference_images, reference_image_urls,
                                system_prompt)
        data = client.generate_async(payload)
        task_id = data.get("taskId", "")
        status = data.get("status", "pending")
        print(f"[Labnana] task submitted: {task_id} ({status})")
        return (task_id, status)


class LabnanaGetTaskNode:
    """Fetch (optionally wait for) a task and download its images."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "client": ("LABNANA_CLIENT",),
                "task_id": ("STRING", {"default": "", "forceInput": False}),
                "wait_for_completion": ("BOOLEAN", {"default": True}),
                "poll_interval": ("FLOAT", {"default": 5.0, "min": 1.0,
                                            "max": 60.0, "step": 0.5}),
                "timeout": ("FLOAT", {"default": 600.0, "min": 30.0,
                                      "max": 3600.0, "step": 10.0}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("images", "status", "image_urls", "info_json")
    FUNCTION = "fetch"
    CATEGORY = f"{CATEGORY_ROOT}/Tasks"
    DESCRIPTION = ("GET /openapi/v1/images/generation/tasks/{taskId} — poll a "
                   "task and download its images once successful.")

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")  # task state lives server-side

    def fetch(self, client, task_id, wait_for_completion, poll_interval,
              timeout):
        task_id = (task_id or "").strip()
        if wait_for_completion:
            task = client.wait_for_task(task_id, poll_interval=poll_interval,
                                        timeout=timeout)
        else:
            task = client.get_task(task_id)

        status = task.get("status", "unknown")
        images = task.get("images") or []
        urls = [img["url"] for img in images if img.get("url")]
        if status == "success" and urls:
            pils = [bytes_to_pil(client.download(u)) for u in urls]
            batch = pils_to_image_batch(pils)
        elif status == "success":
            raise LabnanaError(f"Task {task_id} succeeded but has no images")
        else:
            raise LabnanaError(
                f"Task {task_id} is not finished (status: {status}"
                f"{', failMsg: ' + task['failMsg'] if task.get('failMsg') else ''}). "
                "Enable wait_for_completion to block until it completes.")
        return (batch, status, "\n".join(urls), _pretty(task))


class LabnanaListTasksNode:
    """Browse generation history."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "client": ("LABNANA_CLIENT",),
                "page": ("INT", {"default": 1, "min": 1, "max": 10000}),
                "page_size": ("INT", {"default": 20, "min": 1, "max": 100}),
                "status_filter": (["all"] + TASK_STATUSES, {"default": "all"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("tasks_json", "latest_task_id", "total")
    FUNCTION = "list_tasks"
    CATEGORY = f"{CATEGORY_ROOT}/Tasks"
    OUTPUT_NODE = True
    DESCRIPTION = "GET /openapi/v1/images/generation/tasks — paged task history."

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def list_tasks(self, client, page, page_size, status_filter):
        status = None if status_filter == "all" else status_filter
        data = client.list_tasks(page=page, page_size=page_size, status=status)
        items = data.get("items") or []
        latest = items[0].get("taskId", "") if items else ""
        info = _pretty(data)
        print(f"[Labnana] tasks (page {page}):\n{info}")
        return (info, latest, int(data.get("total", 0)))


# -------------------------------------------------------------------- helpers


class LabnanaLoadImageFromURLNode:
    """Utility: turn result URLs (or any image URLs) back into IMAGE tensors."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "urls": ("STRING", {
                    "multiline": True, "default": "",
                    "tooltip": "One image URL per line."}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "load"
    CATEGORY = f"{CATEGORY_ROOT}/Helpers"
    DESCRIPTION = "Downloads image URLs (e.g. async task results) as an IMAGE batch."

    def load(self, urls):
        import requests
        url_list = [u.strip() for u in urls.replace(",", "\n").splitlines()
                    if u.strip()]
        if not url_list:
            raise ValueError("No URLs given")
        pils = []
        for u in url_list:
            resp = requests.get(u, timeout=120)
            resp.raise_for_status()
            pils.append(bytes_to_pil(resp.content))
        return (pils_to_image_batch(pils),)


NODE_CLASS_MAPPINGS = {
    "LabnanaClient": LabnanaClientNode,
    "LabnanaSubscription": LabnanaSubscriptionNode,
    "LabnanaImageGeneration": LabnanaImageGenerationNode,
    "LabnanaImageGenerationAsync": LabnanaImageGenerationAsyncNode,
    "LabnanaEstimateCredits": LabnanaEstimateCreditsNode,
    "LabnanaSubmitTask": LabnanaSubmitTaskNode,
    "LabnanaGetTask": LabnanaGetTaskNode,
    "LabnanaListTasks": LabnanaListTasksNode,
    "LabnanaLoadImageFromURL": LabnanaLoadImageFromURLNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LabnanaClient": "Labnana API Client",
    "LabnanaSubscription": "Labnana Subscription Info",
    "LabnanaImageGeneration": "Labnana Image Generation",
    "LabnanaImageGenerationAsync": "Labnana Image Generation (Async)",
    "LabnanaEstimateCredits": "Labnana Estimate Credits",
    "LabnanaSubmitTask": "Labnana Submit Task",
    "LabnanaGetTask": "Labnana Get Task",
    "LabnanaListTasks": "Labnana List Tasks",
    "LabnanaLoadImageFromURL": "Labnana Load Image From URL",
}
