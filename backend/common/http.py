"""Shared HTTP helper for external providers.

Every provider call goes through here so timeouts and retry behaviour are
consistent and BOUNDED: the whole analyze request must finish well inside
the server worker timeout, so the default is one retry with short backoff
on transient failures — connection errors, timeouts, HTTP 5xx and HTTP 429
(rate limited). For 429 responses the provider's ``Retry-After`` header is
honoured when present (capped at 3s). Other HTTP 4xx responses are raised
immediately — retrying them cannot help. Providers pass explicit
``timeout`` / ``retries`` budgets suited to their role in the request.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger("apps.providers.http")

MAX_RETRY_AFTER_SECONDS = 3.0
BASE_BACKOFF_SECONDS = 0.5


class ProviderError(Exception):
    """An external provider could not deliver usable data."""


def _retry_delay(response: requests.Response | None, attempt: int) -> float:
    """Backoff for the next attempt: 0.5s, 1s, 2s — or Retry-After if given."""
    if response is not None:
        raw = response.headers.get("Retry-After")
        if raw:
            try:
                return min(float(raw), MAX_RETRY_AFTER_SECONDS)
            except ValueError:
                pass
    return BASE_BACKOFF_SECONDS * (2 ** attempt)


def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    retries: int = 1,
) -> Any:
    """GET `url` and return parsed JSON, retrying transient failures once."""
    timeout = timeout if timeout is not None else settings.PROVIDER_TIMEOUT_SECONDS
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        response: requests.Response | None = None
        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=timeout
            )
            if response.status_code == 429 or response.status_code >= 500:
                raise ProviderError(
                    f"{url} returned HTTP {response.status_code}"
                )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ProviderError) as exc:
            last_exc = exc
            logger.warning(
                "provider request failed attempt=%d url=%s error=%s",
                attempt + 1,
                url,
                exc,
            )
            if isinstance(exc, requests.HTTPError) and exc.response is not None \
                    and 400 <= exc.response.status_code < 500 \
                    and exc.response.status_code != 429:
                break  # client error other than rate limiting: do not retry
            if attempt < retries:
                time.sleep(_retry_delay(response, attempt))
    raise ProviderError(f"Provider request failed for {url}: {last_exc}")
