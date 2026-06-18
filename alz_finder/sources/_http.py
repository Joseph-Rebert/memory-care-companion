"""Shared HTTP helper with polite retries and 429 backoff."""
from __future__ import annotations

import os
import time

import requests

CONTACT = os.environ.get("CONTACT_EMAIL", "you@example.com")
USER_AGENT = f"alz-finder/0.1 (mailto:{CONTACT})"

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})


def get(url: str, params: dict | None = None, headers: dict | None = None,
        timeout: int = 30, max_retries: int = 5) -> requests.Response:
    """GET with exponential backoff on 429 / 5xx and on network timeouts."""
    delay = 2.0
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = _session.get(url, params=params, headers=headers, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == max_retries - 1:
                resp.raise_for_status()
            retry_after = resp.headers.get("Retry-After")
            sleep = float(retry_after) if retry_after and retry_after.isdigit() else delay
            time.sleep(sleep)
            delay *= 2
            continue
        resp.raise_for_status()
        return resp
    if last_exc:
        raise last_exc
    raise RuntimeError("unreachable")
