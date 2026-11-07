"""Backup weather provider: MET Norway Locationforecast API (keyless).

Used ONLY when the primary provider (Open-Meteo) fails — for example when
it rate-limits the hosting platform's shared egress IP, as seen on Render
on 2026-11-07. MET Norway (the Norwegian Meteorological Institute, the
service behind yr.no) publishes a global hourly forecast and identifies
clients by User-Agent instead of by API key or strict per-IP quotas.

Unit / field normalization to the shared ``HourlyForecast`` shape:
- ``wind_speed`` is m/s -> converted to mph (x 2.23694).
- ``precipitation_amount`` is TOTAL precipitation in mm for the forecast
  period (next 1 hour, else next 6 hours divided by 6). MET Norway does
  not split rain from snow, so the period's ``symbol_code`` classifies
  it: symbols containing "snow" or "sleet" count the amount as snow,
  everything else as rain. Snow water-equivalent is converted to snow
  depth with the standard 10:1 ratio (1 mm water ~ 10 mm snow).
  This split is an approximation, documented here and in the README; it
  applies only on the fallback path.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from django.conf import settings

from apps.weather.providers.open_meteo import HourlyForecast
from common.http import ProviderError, get_json

logger = logging.getLogger("apps.weather.providers.met_norway")

# MET Norway's terms require an identifying User-Agent with the product
# name and a contact/URL; requests without one are rejected.
USER_AGENT = (
    "weather-aware-truck-routing/1.0 "
    "github.com/azlan98-not/weather-aware-truck-routing"
)
MS_TO_MPH = 2.23694
MM_PER_INCH = 25.4
SNOW_DEPTH_RATIO = 10.0  # 1 mm water equivalent ~ 10 mm of snow depth
MAX_WORKERS = 8


def _parse_time(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _precip_block(data: dict) -> tuple[float | None, str]:
    """(mm per hour, symbol_code) from next_1_hours, else next_6_hours."""
    block = data.get("next_1_hours")
    hours = 1.0
    if not block:
        block = data.get("next_6_hours")
        hours = 6.0
    if not block:
        return None, ""
    amount = (block.get("details") or {}).get("precipitation_amount")
    symbol = (block.get("summary") or {}).get("symbol_code") or ""
    if amount is None:
        return None, symbol
    return float(amount) / hours, symbol


def _location_forecasts(payload: dict) -> dict[datetime, HourlyForecast]:
    """Map hour -> forecast for one MET Norway locationforecast response."""
    series = (payload.get("properties") or {}).get("timeseries") or []
    forecasts: dict[datetime, HourlyForecast] = {}
    for entry in series:
        data = entry.get("data") or {}
        instant = (data.get("instant") or {}).get("details") or {}
        wind_ms = instant.get("wind_speed")
        wind_mph = None if wind_ms is None else float(wind_ms) * MS_TO_MPH
        precip_mm_hr, symbol = _precip_block(data)
        rain_in: float | None = None
        snow_in: float | None = None
        if precip_mm_hr is not None:
            if "snow" in symbol or "sleet" in symbol:
                rain_in = 0.0
                snow_in = precip_mm_hr * SNOW_DEPTH_RATIO / MM_PER_INCH
            else:
                rain_in = precip_mm_hr / MM_PER_INCH
                snow_in = 0.0
        try:
            hour = _parse_time(entry["time"])
        except (KeyError, ValueError):
            continue
        forecasts[hour] = HourlyForecast(
            wind_mph=wind_mph,
            rain_in_per_hr=rain_in,
            snow_in_per_hr=snow_in,
        )
    return forecasts


def _fetch_one(coordinate: tuple[float, float]) -> dict[datetime, HourlyForecast]:
    lat, lon = coordinate
    url = f"{settings.MET_NORWAY_BASE_URL}/weatherapi/locationforecast/2.0/compact"
    # No retries on the fallback path: it runs only after the primary
    # provider already burned the retry budget, and the request as a
    # whole must stay well inside the server worker timeout.
    payload = get_json(
        url,
        params={"lat": round(lat, 4), "lon": round(lon, 4)},
        headers={"User-Agent": USER_AGENT},
        timeout=6,
        retries=0,
    )
    if not isinstance(payload, dict):
        raise ProviderError("MET Norway returned a non-object payload")
    return _location_forecasts(payload)


def fetch_hourly_forecasts(
    coordinates: list[tuple[float, float]],
) -> list[dict[datetime, HourlyForecast]]:
    """Hourly forecasts for many coordinates, one call per coordinate.

    Same return shape as the Open-Meteo provider: one {hour: forecast}
    dict per input coordinate, in order. A coordinate whose call fails
    degrades to an empty dict (its checkpoints become UNKNOWN); if EVERY
    coordinate fails, ProviderError is raised so the caller can degrade
    the whole set exactly as it does for a primary-provider failure.
    """
    if not coordinates:
        return []
    results: list[dict[datetime, HourlyForecast]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(_fetch_one, coord) for coord in coordinates]
        for coord, future in zip(coordinates, futures):
            try:
                results.append(future.result())
            except ProviderError as exc:
                logger.warning(
                    "met norway fallback failed for %s: %s", coord, exc
                )
                results.append({})
    if all(not forecasts for forecasts in results):
        raise ProviderError("MET Norway fallback failed for every coordinate")
    return results
