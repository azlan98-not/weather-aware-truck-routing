"""Weather provider: Open-Meteo forecast API (keyless).

Units are requested explicitly and normalized here:
- wind_speed_10m  -> mph            (wind_speed_unit=mph)
- rain            -> inches/hour    (precipitation_unit=inch)
- snowfall        -> returned in cm, converted to inches (÷ 2.54)

All coordinates for a route are batched into ONE call using Open-Meteo's
comma-separated latitude/longitude lists.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from django.conf import settings

from common.http import ProviderError, get_json

logger = logging.getLogger("apps.weather.providers.open_meteo")

CM_PER_INCH = 2.54
HOURLY_VARIABLES = "wind_speed_10m,rain,snowfall"


@dataclass(frozen=True)
class HourlyForecast:
    """Weather values for one coordinate at one hour (all optional)."""

    wind_mph: float | None
    rain_in_per_hr: float | None
    snow_in_per_hr: float | None


def _parse_time(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _value(series: list, idx: int) -> float | None:
    if series is None or idx >= len(series):
        return None
    value = series[idx]
    return None if value is None else float(value)


def _location_forecasts(location: dict) -> dict[datetime, HourlyForecast]:
    """Map hour -> forecast for one location block of an Open-Meteo response."""
    hourly = location.get("hourly") or {}
    times = hourly.get("time") or []
    wind = hourly.get("wind_speed_10m")
    rain = hourly.get("rain")
    snow_cm = hourly.get("snowfall")
    forecasts: dict[datetime, HourlyForecast] = {}
    for idx, raw_time in enumerate(times):
        snow = _value(snow_cm, idx)
        forecasts[_parse_time(raw_time)] = HourlyForecast(
            wind_mph=_value(wind, idx),
            rain_in_per_hr=_value(rain, idx),
            snow_in_per_hr=None if snow is None else snow / CM_PER_INCH,
        )
    return forecasts


def fetch_hourly_forecasts(
    coordinates: list[tuple[float, float]],
) -> list[dict[datetime, HourlyForecast]]:
    """Batched hourly forecasts for many coordinates in a single API call.

    Returns one {hour: HourlyForecast} dict per input coordinate, in order.
    Raises ProviderError on provider failure.
    """
    if not coordinates:
        return []
    url = f"{settings.OPEN_METEO_BASE_URL}/v1/forecast"
    params = {
        "latitude": ",".join(str(lat) for lat, _ in coordinates),
        "longitude": ",".join(str(lon) for _, lon in coordinates),
        "hourly": HOURLY_VARIABLES,
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "UTC",
        "forecast_days": 16,
    }
    data = get_json(url, params=params)
    locations = data if isinstance(data, list) else [data]
    if len(locations) != len(coordinates):
        logger.warning(
            "open-meteo returned %d locations for %d coordinates",
            len(locations),
            len(coordinates),
        )
    forecasts: list[dict[datetime, HourlyForecast]] = []
    for idx in range(len(coordinates)):
        if idx < len(locations) and isinstance(locations[idx], dict) \
                and "hourly" in locations[idx]:
            forecasts.append(_location_forecasts(locations[idx]))
        else:
            forecasts.append({})
    return forecasts
