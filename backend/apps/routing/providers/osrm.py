"""Routing provider: OSRM demo server (keyless).

Primary request asks OSRM for up to 3 alternatives. OSRM's public demo
server frequently returns fewer (verified live 2026-11-06: Chicago →
St Louis returned only 2), so a documented fallback generates additional
GENUINE alternatives by routing through offset detour waypoints — points
offset perpendicular to the straight origin–destination line at ~35% and
~65% of the way, on opposite sides. Detour routes are real OSRM routes
through real roads; nothing is fabricated or duplicated. Candidates are
deduplicated by a geometry/distance signature. If fewer than 3 distinct
routes exist even after the fallback, the caller returns what exists plus
an explicit warning (handled in the analysis service).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from django.conf import settings

from common.http import ProviderError, get_json

logger = logging.getLogger("apps.routing.providers.osrm")

METERS_PER_MILE = 1609.344
TARGET_ALTERNATIVES = 3


@dataclass
class ProviderRoute:
    """One route as returned by the routing provider."""

    distance_miles: float
    duration_seconds: float
    geometry: list[list[float]]          # [[lat, lon], ...]
    summary: str
    waypoint_names: list[str] = field(default_factory=list)

    def signature(self) -> tuple:
        """Deduplication signature: rounded distance + a geometry fingerprint."""
        points = self.geometry
        if not points:
            return (round(self.distance_miles, 1), ())
        mid = points[len(points) // 2]
        quarter = points[len(points) // 4]
        return (
            round(self.distance_miles, 1),
            (round(points[0][0], 3), round(points[0][1], 3)),
            (round(quarter[0], 3), round(quarter[1], 3)),
            (round(mid[0], 3), round(mid[1], 3)),
            (round(points[-1][0], 3), round(points[-1][1], 3)),
        )


def _parse_route(raw: dict) -> ProviderRoute:
    coords = raw["geometry"]["coordinates"]  # GeoJSON: [lon, lat]
    geometry = [[float(lat), float(lon)] for lon, lat in coords]
    legs = raw.get("legs") or []
    summaries = [leg.get("summary", "") for leg in legs if leg.get("summary")]
    summary = " via ".join(summaries) if summaries else "Route"
    return ProviderRoute(
        distance_miles=float(raw["distance"]) / METERS_PER_MILE,
        duration_seconds=float(raw["duration"]),
        geometry=geometry,
        summary=summary,
    )


def _request_routes(
    waypoints: list[tuple[float, float]], alternatives: int
) -> list[ProviderRoute]:
    """One OSRM request. `waypoints` are (lat, lon) pairs."""
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in waypoints)
    url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{coord_str}"
    data = get_json(
        url,
        params={
            "alternatives": alternatives,
            "geometries": "geojson",
            "overview": "full",
            "steps": "false",
        },
        timeout=8,
        retries=1,
    )
    if data.get("code") != "Ok":
        raise ProviderError(
            f"OSRM routing failed: {data.get('message') or data.get('code')}"
        )
    return [_parse_route(raw) for raw in data.get("routes", [])]


def _offset_point(
    origin: tuple[float, float],
    destination: tuple[float, float],
    fraction: float,
    side: int,
    offset_fraction: float = 0.12,
) -> tuple[float, float]:
    """Point at `fraction` along the straight line, offset perpendicular.

    `side` is +1 or -1. The offset magnitude is `offset_fraction` of the
    straight-line length (with a floor so short trips still detour visibly).
    Coordinates are (lat, lon); the perpendicular is computed in degrees,
    which is adequate for generating a detour waypoint (OSRM snaps it to
    the nearest road).
    """
    lat1, lon1 = origin
    lat2, lon2 = destination
    base_lat = lat1 + (lat2 - lat1) * fraction
    base_lon = lon1 + (lon2 - lon1) * fraction
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    length = math.hypot(d_lat, d_lon) or 1e-9
    # Perpendicular unit vector.
    p_lat = -d_lon / length
    p_lon = d_lat / length
    offset = max(length * offset_fraction, 0.05)
    return (base_lat + side * p_lat * offset, base_lon + side * p_lon * offset)


def _dedupe(routes: list[ProviderRoute]) -> list[ProviderRoute]:
    seen: set = set()
    unique: list[ProviderRoute] = []
    for route in routes:
        sig = route.signature()
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(route)
    return unique


def fetch_routes(
    origin: tuple[float, float],
    destination: tuple[float, float],
    target: int = TARGET_ALTERNATIVES,
) -> tuple[list[ProviderRoute], bool]:
    """Fetch up to `target` distinct genuine routes.

    Returns (routes, fallback_used). Raises ProviderError when the provider
    cannot produce even one route.
    """
    routes = _dedupe(_request_routes([origin, destination], alternatives=target))
    fallback_used = False

    if len(routes) < target:
        fallback_used = True
        # Detour waypoints: 35% along, offset to one side; 65% along, other side.
        detours = [
            _offset_point(origin, destination, 0.35, side=+1),
            _offset_point(origin, destination, 0.65, side=-1),
        ]
        for waypoint in detours:
            if len(routes) >= target:
                break
            try:
                extra = _request_routes([origin, waypoint, destination], alternatives=0)
            except ProviderError as exc:
                logger.warning("detour routing attempt failed: %s", exc)
                continue
            for route in extra:
                route.summary = f"{route.summary} (detour alternative)"
            routes = _dedupe(routes + extra)

    if not routes:
        raise ProviderError("Routing provider returned no routes for this trip.")
    routes.sort(key=lambda r: r.duration_seconds)
    return routes[:target], fallback_used
