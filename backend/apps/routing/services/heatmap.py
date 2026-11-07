"""Corridor weather heatmap service.

Samples the supplied route geometry at the checkpoint interval and
evaluates REAL forecast weather at: departure + hour_offset + travel time
to that point. Travel time uses the same constant-average-speed assumption
as the analysis (fraction of the route's total duration). When the caller
does not supply the route duration, a documented 55 mph highway-speed
estimate is used instead — the frontend always supplies the selected
route's real duration.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from apps.risk.services import risk as risk_engine
from apps.routing.services.geometry import (
    build_checkpoint_locations,
    cumulative_distances,
)
from apps.weather.services.weather_service import fetch_weather_for_points

logger = logging.getLogger("apps.routing.services.heatmap")

FALLBACK_SPEED_MPH = 55.0


def build_heatmap(
    geometry: list[list[float]],
    departure: datetime,
    hour_offset: float,
    load_weight_lb: float,
    interval_miles: int,
    duration_minutes: float | None = None,
) -> dict[str, Any]:
    """Return {points: [...], forecast_time} for one slider position."""
    cumulative = cumulative_distances(geometry)
    total_miles = cumulative[-1]
    if duration_minutes is not None:
        duration_seconds = duration_minutes * 60.0
    else:
        duration_seconds = (total_miles / FALLBACK_SPEED_MPH) * 3600.0

    base_time = departure + timedelta(hours=hour_offset)
    locations = build_checkpoint_locations(
        geometry, total_miles, duration_seconds, base_time, interval_miles
    )
    points = [(loc.latitude, loc.longitude) for loc in locations]
    etas = [loc.eta for loc in locations]
    weather = fetch_weather_for_points(points, etas)

    result_points: list[dict[str, Any]] = []
    for loc, wx in zip(locations, weather):
        result = risk_engine.evaluate_checkpoint(
            wx.wind_mph if wx.available else None,
            wx.rain_in_per_hr if wx.available else None,
            wx.snow_in_per_hr if wx.available else None,
            load_weight_lb,
        )
        result_points.append(
            {
                "latitude": round(loc.latitude, 6),
                "longitude": round(loc.longitude, 6),
                "distance_miles": round(loc.distance_miles, 2),
                "risk_level": result.level,
                "risk_score": result.score,
                "wind_mph": None if wx.wind_mph is None else round(wx.wind_mph, 2),
                "rain_in_per_hr": None if wx.rain_in_per_hr is None else round(wx.rain_in_per_hr, 3),
                "snow_in_per_hr": None if wx.snow_in_per_hr is None else round(wx.snow_in_per_hr, 3),
            }
        )

    return {
        "points": result_points,
        "forecast_time": base_time.isoformat().replace("+00:00", "Z"),
    }
