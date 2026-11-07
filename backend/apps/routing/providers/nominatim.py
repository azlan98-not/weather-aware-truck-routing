"""Geocoding provider: OpenStreetMap Nominatim (keyless).

Usage policy: a descriptive User-Agent header is required by Nominatim;
requests are made once per analyze call (origin + destination).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

from common.http import ProviderError, get_json

logger = logging.getLogger("apps.routing.providers.nominatim")

USER_AGENT = "WeatherAwareTruckRouting/1.0 (Spotter AI assessment)"


class GeocodingError(ProviderError):
    """The place could not be resolved to coordinates."""


@dataclass(frozen=True)
class GeocodedPlace:
    query: str
    display_name: str
    latitude: float
    longitude: float


def geocode(query: str) -> GeocodedPlace:
    """Resolve a free-text place to coordinates.

    Raises GeocodingError when Nominatim finds no match, so the API layer
    can return a clear 400 validation error.
    """
    url = f"{settings.NOMINATIM_BASE_URL}/search"
    results = get_json(
        url,
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    if not results:
        raise GeocodingError(f"Location not found: {query!r}")
    top = results[0]
    try:
        return GeocodedPlace(
            query=query,
            display_name=top.get("display_name", query),
            latitude=float(top["lat"]),
            longitude=float(top["lon"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError(f"Malformed geocoding result for {query!r}") from exc
