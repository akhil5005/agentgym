"""A tiny HTTP client for uploading results to the backend.

The engine only ever *sends* finished results. It never asks the backend what to
do, so this client has no read methods beyond a health check.

Nothing here raises on a network failure: a run that took two minutes of model
time must not be lost because a laptop's wifi dropped. Failures come back as
values the caller reports, and the JSONL file on disk stays the source of truth.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (1.0, 2.0)  # waits between attempt 1->2 and 2->3
TIMEOUT_SECONDS = 30.0

Outcome = Literal["uploaded", "duplicate", "failed"]


@dataclass(frozen=True)
class UploadResult:
    """What happened to one upload."""

    outcome: Outcome
    detail: str = ""

    @property
    def ok(self) -> bool:
        """True when the row is in the database — whether we just put it there
        or a previous run already did."""
        return self.outcome in ("uploaded", "duplicate")


class BackendClient:
    """Posts tasks and episodes to the AgentGym backend."""

    def __init__(self, api_url: str, api_key: str) -> None:
        # Strip the trailing slash so joining paths never produces a double one.
        self.api_url = api_url.rstrip("/")
        self._headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    def health(self) -> tuple[bool, str]:
        """Check the backend is reachable before uploading a whole run."""
        try:
            response = httpx.get(f"{self.api_url}/api/health", timeout=10.0)
        except httpx.HTTPError as exc:
            return False, f"cannot reach {self.api_url}: {exc}"
        if response.status_code != 200:
            return False, f"{self.api_url}/api/health returned {response.status_code}"
        return True, "ok"

    def put_task(self, task_id: str, payload: dict[str, Any]) -> UploadResult:
        """Upsert one task's public metadata."""
        return self._send("PUT", f"/api/tasks/{task_id}", payload)

    def post_episode(self, payload: dict[str, Any]) -> UploadResult:
        """Store one episode and its trajectory."""
        return self._send("POST", "/api/episodes", payload)

    # --- the one place that talks to the network -----------------------------

    def _send(self, method: str, path: str, payload: dict[str, Any]) -> UploadResult:
        """Send a request, retrying only the failures worth retrying."""
        url = f"{self.api_url}{path}"
        last_detail = "no attempt was made"

        for attempt in range(MAX_ATTEMPTS):
            try:
                response = httpx.request(
                    method,
                    url,
                    json=payload,
                    headers=self._headers,
                    timeout=TIMEOUT_SECONDS,
                )
            except httpx.HTTPError as exc:
                last_detail = f"network error: {exc}"
            else:
                if response.status_code in (200, 201):
                    return UploadResult("uploaded")

                if response.status_code == 409:
                    # Already stored. Re-uploading a file is meant to be safe,
                    # so this is a success from the caller's point of view.
                    return UploadResult("duplicate", "already uploaded")

                detail = f"HTTP {response.status_code}: {_short_body(response)}"

                # 4xx other than 429 means the request itself is wrong, so
                # retrying would just send the same bad request three times.
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    return UploadResult("failed", detail)

                last_detail = detail

            if attempt < len(BACKOFF_SECONDS):
                time.sleep(BACKOFF_SECONDS[attempt])

        return UploadResult("failed", f"gave up after {MAX_ATTEMPTS} attempts; {last_detail}")


def _short_body(response: httpx.Response) -> str:
    """A readable one-liner from an error response."""
    try:
        data = response.json()
    except ValueError:
        return response.text[:200].replace("\n", " ")
    if isinstance(data, dict) and "detail" in data:
        return str(data["detail"])[:300]
    return str(data)[:300]
