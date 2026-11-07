"""Shared HTTP helper for external providers.

Every provider call goes through here so timeouts and retry behaviour are
consistent: 10-second timeout, exactly one retry on a transient failure
(connection error, timeout, or HTTP 5xx). HTTP 4xx responses are raised
immediately — retrying them cannot help.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger("apps.providers.http")


class ProviderError(Exception):
    """An external provider could not deliver usable data."""


def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    retries: int = 1,
) -> Any:
    """GET `url` and return parsed JSON, with one retry on transient failure."""
    timeout = timeout if timeout is not None else settings.PROVIDER_TIMEOUT_SECONDS
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=timeout
            )
            if response.status_code >= 500:
                raise ProviderError(f"{url} returned HTTP {response.status_code}")
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
                    and 400 <= exc.response.status_code < 500:
                break  # client error: do not retry
            if attempt < retries:
                time.sleep(0.5)
    raise ProviderError(f"Provider request failed for {url}: {last_exc}")
