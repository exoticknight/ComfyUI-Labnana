"""Thin HTTP client for the Labnana OpenAPI (https://api.labnana.com).

Handles Bearer auth, the {code, message, data} envelope, rate-limit retries
(error code 29998 / HTTP 429 with 20-30s exponential backoff as documented),
and exposes one method per endpoint.
"""

import os
import random
import time

import requests

DEFAULT_BASE_URL = "https://api.labnana.com"
API_KEY_ENV = "LABNANA_API_KEY"

# Documented error codes -> remediation hints appended to error messages.
ERROR_HINTS = {
    21007: "API key is invalid. Check it at https://labnana.com/api-keys",
    26004: "Insufficient credits. Top up or upgrade at https://labnana.com/pricing",
    29003: "Parameter error. Check model/provider/imageSize/aspectRatio combination.",
    29998: "Rate limited. The client already retried with backoff; try again later "
           "(free-tier traffic is throttled during busy periods).",
}


class LabnanaError(RuntimeError):
    """API-level failure with the Labnana error code attached."""

    def __init__(self, message, code=None, http_status=None):
        self.code = code
        self.http_status = http_status
        hint = ERROR_HINTS.get(code)
        full = f"Labnana API error {code if code is not None else http_status}: {message}"
        if hint:
            full += f" | {hint}"
        super().__init__(full)


class LabnanaClient:
    def __init__(self, api_key="", base_url=DEFAULT_BASE_URL, timeout=300,
                 max_retries=3):
        api_key = (api_key or "").strip() or os.environ.get(API_KEY_ENV, "").strip()
        if not api_key:
            raise LabnanaError(
                "No API key provided. Fill the api_key field on the Labnana API "
                f"Client node or set the {API_KEY_ENV} environment variable. "
                "Keys are created at https://labnana.com/api-keys"
            )
        self.api_key = api_key
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ComfyUI-Labnana/1.0",
        })

    # ------------------------------------------------------------------ core

    def _request(self, method, path, json_body=None, params=None):
        url = f"{self.base_url}{path}"
        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.request(
                    method, url, json=json_body, params=params,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_err = LabnanaError(f"Network error calling {path}: {exc}")
                # Network hiccups are worth one quick retry, not a long backoff.
                if attempt < self.max_retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise last_err

            try:
                payload = resp.json()
            except ValueError:
                raise LabnanaError(
                    f"Non-JSON response from {path} "
                    f"(HTTP {resp.status_code}): {resp.text[:300]}",
                    http_status=resp.status_code,
                )

            code = payload.get("code") if isinstance(payload, dict) else None

            rate_limited = resp.status_code == 429 or code == 29998
            if rate_limited and attempt < self.max_retries:
                # Docs recommend 20-30s exponential backoff.
                delay = min(20 * (2 ** attempt), 120) + random.uniform(0, 5)
                print(f"[Labnana] rate limited, retrying in {delay:.0f}s "
                      f"(attempt {attempt + 1}/{self.max_retries})")
                time.sleep(delay)
                continue

            if not resp.ok:
                raise LabnanaError(
                    payload.get("message", resp.text[:300])
                    if isinstance(payload, dict) else resp.text[:300],
                    code=code, http_status=resp.status_code,
                )

            # Envelope endpoints report failures with code != 0 even on HTTP 200.
            # The sync generation endpoint returns a Gemini-style body without
            # a `code` field, so only treat explicit non-zero codes as errors.
            if isinstance(payload, dict) and isinstance(code, int) and code != 0:
                raise LabnanaError(payload.get("message", ""), code=code,
                                   http_status=resp.status_code)

            return payload

        raise last_err or LabnanaError(f"Request to {path} failed after retries")

    @staticmethod
    def _data(payload):
        return payload.get("data", {}) if isinstance(payload, dict) else {}

    # ------------------------------------------------------------- endpoints

    def get_subscription(self):
        """GET /openapi/v1/user/subscription -> data dict."""
        return self._data(self._request("GET", "/openapi/v1/user/subscription"))

    def estimate_credits(self, payload):
        """POST /openapi/v1/images/generation/estimate-credits -> data dict."""
        return self._data(self._request(
            "POST", "/openapi/v1/images/generation/estimate-credits",
            json_body=payload))

    def generate(self, payload):
        """POST /openapi/v1/images/generation -> Gemini-style response dict."""
        return self._request("POST", "/openapi/v1/images/generation",
                             json_body=payload)

    def generate_async(self, payload):
        """POST /openapi/v1/images/generation/async -> {taskId, status}."""
        return self._data(self._request(
            "POST", "/openapi/v1/images/generation/async", json_body=payload))

    def get_task(self, task_id):
        """GET /openapi/v1/images/generation/tasks/{taskId} -> task dict."""
        if not task_id:
            raise LabnanaError("task_id is empty")
        return self._data(self._request(
            "GET", f"/openapi/v1/images/generation/tasks/{task_id}"))

    def list_tasks(self, page=1, page_size=20, status=None):
        """GET /openapi/v1/images/generation/tasks -> {items, page, total}."""
        params = {"page": page, "pageSize": page_size}
        if status:
            params["status"] = status
        return self._data(self._request(
            "GET", "/openapi/v1/images/generation/tasks", params=params))

    def wait_for_task(self, task_id, poll_interval=5.0, timeout=600.0,
                      progress_cb=None):
        """Poll a task until success/fail. Returns the final task dict."""
        deadline = time.monotonic() + timeout
        while True:
            task = self.get_task(task_id)
            status = task.get("status", "")
            if progress_cb:
                progress_cb(status, task)
            if status == "success":
                return task
            if status == "fail":
                raise LabnanaError(
                    f"Task {task_id} failed: {task.get('failMsg') or 'no failMsg'}")
            if time.monotonic() >= deadline:
                raise LabnanaError(
                    f"Timed out after {timeout:.0f}s waiting for task {task_id} "
                    f"(last status: {status or 'unknown'}). "
                    "Use the 'Labnana Get Task' node later to fetch the result.")
            time.sleep(max(poll_interval, 1.0))

    def download(self, url):
        """Download a result image (public URL) -> bytes."""
        resp = requests.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.content
