"""Weather lookup service: weather at each checkpoint's estimated arrival.

The forecast hour used is the ETA rounded to the NEAREST hour. If that hour
is outside the provider's forecast horizon, or any measurement is missing,
the checkpoint is marked unavailable — callers must treat it as UNKNOWN
risk, never as safe.

Provider order: Open-Meteo (primary, one batched call) -> MET Norway
(backup, one call per point). The backup exists because Open-Meteo
rate-limits by source IP and the hosted backend shares its egress IP with
many other tenants of the hosting platform; MET Norway identifies clients
by User-Agent instead. If both providers fail, every point degrades to
UNAVAILABLE — the analysis still completes and those miles are reported
as UNKNOWN risk instead of the whole request failing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from apps.weather.providers import met_norway, open_meteo
from apps.weather.providers.open_meteo import HourlyForecast
from common.http import ProviderError

logger = logging.getLogger("apps.weather.services")


@dataclass(frozen=True)
class CheckpointWeather:
    wind_mph: float | None
    rain_in_per_hr: float | None
    snow_in_per_hr: float | None
    available: bool


UNAVAILABLE = CheckpointWeather(None, None, None, False)


def round_to_nearest_hour(dt: datetime) -> datetime:
    base = dt.replace(minute=0, second=0, microsecond=0)
    if dt - base >= timedelta(minutes=30):
        base += timedelta(hours=1)
    return base


def weather_at_eta(
    forecasts_by_location: list[dict[datetime, HourlyForecast]],
    etas: list[datetime],
) -> list[CheckpointWeather]:
    """Pair each location's forecast map with its ETA (same list order)."""
    results: list[CheckpointWeather] = []
    for forecasts, eta in zip(forecasts_by_location, etas):
        hour = round_to_nearest_hour(eta)
        forecast = forecasts.get(hour)
        if forecast is None:
            results.append(UNAVAILABLE)
            continue
        if forecast.wind_mph is None or forecast.rain_in_per_hr is None \
                or forecast.snow_in_per_hr is None:
            results.append(UNAVAILABLE)
            continue
        results.append(
            CheckpointWeather(
                wind_mph=forecast.wind_mph,
                rain_in_per_hr=forecast.rain_in_per_hr,
                snow_in_per_hr=forecast.snow_in_per_hr,
                available=True,
            )
        )
    return results


def _forecast_days_needed(etas: list[datetime]) -> int:
    """Days of forecast (counted from today, UTC) covering the latest ETA.

    Keeps provider requests small: a trip departing tomorrow needs ~3 days
    of hourly data, not the provider's full 16-day horizon.
    """
    if not etas:
        return 1
    today = datetime.now(timezone.utc).date()
    latest = max(etas).date()
    return max(1, min(16, (latest - today).days + 2))


def fetch_weather_for_points(
    points: list[tuple[float, float]], etas: list[datetime]
) -> list[CheckpointWeather]:
    """Forecast for all points (primary provider, backup on failure).

    If BOTH providers fail (for example both rate-limit the request),
    every point degrades to UNAVAILABLE — the analysis still completes
    and those miles are reported as UNKNOWN risk, never as safe, instead
    of the whole request failing.
    """
    if not points:
        return []
    try:
        forecasts = open_meteo.fetch_hourly_forecasts(
            points, forecast_days=_forecast_days_needed(etas)
        )
    except ProviderError as exc:
        logger.warning(
            "primary weather provider unavailable (%s); trying backup", exc
        )
        try:
            forecasts = met_norway.fetch_hourly_forecasts(points)
        except ProviderError as backup_exc:
            logger.warning(
                "backup weather provider unavailable; "
                "%d checkpoint(s) marked unknown: %s",
                len(points),
                backup_exc,
            )
            return [UNAVAILABLE] * len(points)
        logger.info(
            "backup weather provider served %d checkpoint(s)", len(points)
        )
    return weather_at_eta(forecasts, etas)
