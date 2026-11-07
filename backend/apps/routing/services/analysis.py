"""Trip analysis orchestration.

Pipeline: geocode origin/destination -> fetch up to 3 genuine routes ->
per route (concurrently): place checkpoints along the geometry, batch-fetch
weather at each checkpoint's ETA, classify risk, summarize risk miles ->
recommendation. Views stay thin; all business logic lives here and in the
risk / recommendation modules.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any

from apps.recommendations.services.recommender import recommend
from apps.risk.services import risk as risk_engine
from apps.routing.providers import nominatim, osrm
from apps.routing.providers.nominatim import GeocodingError
from apps.routing.services.geometry import build_checkpoint_locations
from apps.weather.services.weather_service import fetch_weather_for_points
from common.http import ProviderError

logger = logging.getLogger("apps.routing.services.analysis")

SCORE_TO_MILES_KEY = {
    risk_engine.LOW: "low_miles",
    risk_engine.MODERATE: "moderate_miles",
    risk_engine.HIGH: "high_miles",
    risk_engine.SEVERE: "severe_miles",
    risk_engine.NO_TRAVEL: "no_travel_miles",
}


class AnalysisError(Exception):
    """User-facing failure with an HTTP status and stable error code."""

    def __init__(self, message: str, *, code: str = "analysis_failed", status: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def summarize_route_risk(
    checkpoints: list[dict[str, Any]], total_miles: float
) -> dict[str, Any]:
    """Aggregate checkpoint risks into per-route risk miles.

    Segment rule: checkpoint i's risk applies to the segment starting at its
    distance and ending at the next checkpoint's distance; the final
    checkpoint covers the remaining segment to the route end (zero miles if
    it sits exactly at the end). UNKNOWN segments are excluded from the
    distance-weighted average and reported as unknown_miles, so
    low+moderate+high+severe+no_travel+unknown == total distance.
    """
    summary = {
        "low_miles": 0.0,
        "moderate_miles": 0.0,
        "high_miles": 0.0,
        "severe_miles": 0.0,
        "no_travel_miles": 0.0,
        "unknown_miles": 0.0,
        "average_risk": None,
        "highest_risk": None,
        "risky_checkpoint_count": 0,
    }
    weighted_sum = 0.0
    known_miles = 0.0
    highest_score = 0

    for idx, checkpoint in enumerate(checkpoints):
        next_distance = (
            checkpoints[idx + 1]["distance_miles"]
            if idx + 1 < len(checkpoints)
            else total_miles
        )
        segment_miles = max(0.0, next_distance - checkpoint["distance_miles"])
        score = checkpoint["risk_score"]
        if score is None:
            summary["unknown_miles"] += segment_miles
        else:
            key = SCORE_TO_MILES_KEY[checkpoint["risk_level"]]
            summary[key] += segment_miles
            weighted_sum += segment_miles * score
            known_miles += segment_miles
            if score > highest_score:
                highest_score = score
            if score >= risk_engine.RISK_SCORES[risk_engine.HIGH]:
                summary["risky_checkpoint_count"] += 1

    if known_miles > 0:
        summary["average_risk"] = round(weighted_sum / known_miles, 3)
    if highest_score:
        summary["highest_risk"] = risk_engine.SCORE_LABELS[highest_score]

    for key in (
        "low_miles", "moderate_miles", "high_miles",
        "severe_miles", "no_travel_miles", "unknown_miles",
    ):
        summary[key] = round(summary[key], 3)
    return summary


def _analyze_route(
    index: int,
    provider_route: osrm.ProviderRoute,
    departure: datetime,
    load_weight_lb: float,
    interval_miles: int,
) -> dict[str, Any]:
    """Build the full API representation of one route."""
    total_miles = provider_route.distance_miles
    duration_minutes = provider_route.duration_seconds / 60.0
    locations = build_checkpoint_locations(
        provider_route.geometry,
        total_miles,
        provider_route.duration_seconds,
        departure,
        interval_miles,
    )
    points = [(loc.latitude, loc.longitude) for loc in locations]
    etas = [loc.eta for loc in locations]
    weather = fetch_weather_for_points(points, etas)

    checkpoints: list[dict[str, Any]] = []
    has_no_travel = False
    unsafe_reason: str | None = None
    for loc, wx in zip(locations, weather):
        result = risk_engine.evaluate_checkpoint(
            wx.wind_mph if wx.available else None,
            wx.rain_in_per_hr if wx.available else None,
            wx.snow_in_per_hr if wx.available else None,
            load_weight_lb,
        )
        if result.level == risk_engine.NO_TRAVEL:
            has_no_travel = True
            if unsafe_reason is None:
                unsafe_reason = (
                    f"NO TRAVEL conditions at mile {loc.distance_miles:.0f} "
                    f"(wind {wx.wind_mph:.0f} mph, rain {wx.rain_in_per_hr:.2f} in/hr, "
                    f"snow {wx.snow_in_per_hr:.2f} in/hr, load {load_weight_lb:,.0f} lb)"
                )
        checkpoints.append(
            {
                "distance_miles": round(loc.distance_miles, 2),
                "latitude": round(loc.latitude, 6),
                "longitude": round(loc.longitude, 6),
                "eta": _iso(loc.eta),
                "wind_mph": None if wx.wind_mph is None else round(wx.wind_mph, 2),
                "rain_in_per_hr": None if wx.rain_in_per_hr is None else round(wx.rain_in_per_hr, 3),
                "snow_in_per_hr": None if wx.snow_in_per_hr is None else round(wx.snow_in_per_hr, 3),
                "risk_level": result.level,
                "risk_score": result.score,
                "weather_available": wx.available,
            }
        )

    summary = summarize_route_risk(checkpoints, total_miles)
    arrival = departure + timedelta(seconds=provider_route.duration_seconds)
    return {
        "id": index + 1,
        "summary": provider_route.summary,
        "distance_miles": round(total_miles, 2),
        "duration_minutes": round(duration_minutes, 1),
        "departure_time": _iso(departure),
        "arrival_time": _iso(arrival),
        "geometry": [[round(lat, 6), round(lon, 6)] for lat, lon in provider_route.geometry],
        "checkpoints": checkpoints,
        "risk_summary": summary,
        "has_no_travel": has_no_travel,
        "unsafe_reason": unsafe_reason,
    }


def analyze_trip(
    origin_query: str,
    destination_query: str,
    departure: datetime,
    load_weight_lb: float,
    interval_miles: int,
) -> dict[str, Any]:
    """Run the full analysis and return the API response payload."""
    try:
        origin = nominatim.geocode(origin_query)
        destination = nominatim.geocode(destination_query)
    except GeocodingError as exc:
        raise AnalysisError(str(exc), code="location_not_found", status=400) from exc
    except ProviderError as exc:
        raise AnalysisError(
            "Geocoding provider is unavailable. Please try again.",
            code="provider_unavailable",
            status=502,
        ) from exc

    try:
        provider_routes, fallback_used = osrm.fetch_routes(
            (origin.latitude, origin.longitude),
            (destination.latitude, destination.longitude),
        )
    except ProviderError as exc:
        logger.error("routing provider failed: %s", exc)
        raise AnalysisError(
            "Routing provider is unavailable. Please try again.",
            code="provider_unavailable",
            status=502,
        ) from exc

    warnings: list[str] = []
    if len(provider_routes) < 3:
        warnings.append(
            f"Only {len(provider_routes)} alternative route(s) available from provider "
            "for this origin/destination; genuine additional alternatives could not "
            "be obtained."
        )
    elif fallback_used:
        warnings.append(
            "The routing provider returned fewer than 3 alternatives directly; "
            "additional genuine alternatives were generated via detour waypoints."
        )

    # Routes are independent: analyze them concurrently (each makes one
    # batched weather call).
    with ThreadPoolExecutor(max_workers=min(3, len(provider_routes))) as pool:
        routes = list(
            pool.map(
                lambda args: _analyze_route(
                    args[0], args[1], departure, load_weight_lb, interval_miles
                ),
                list(enumerate(provider_routes)),
            )
        )

    unknown_routes = [
        r["id"] for r in routes if r["risk_summary"]["unknown_miles"] > 0
    ]
    if unknown_routes:
        warnings.append(
            "Weather forecast data was unavailable for part of route(s) "
            f"{', '.join(str(i) for i in unknown_routes)}; those miles are "
            "reported as unknown risk, not as safe."
        )

    recommendation = recommend(routes)
    logger.info(
        "analysis complete origin=%s destination=%s routes=%d recommended=%s",
        origin.display_name,
        destination.display_name,
        len(routes),
        recommendation["route_id"],
    )
    return {
        "routes": routes,
        "recommendation": recommendation,
        "warnings": warnings,
    }
