"""Route-geometry math: cumulative haversine distances, checkpoint placement
and interpolation along the ACTUAL route polyline (never straight-line
origin→destination distances).

ETA model (documented assumption): constant average speed — a checkpoint's
ETA is departure + total_duration × (checkpoint_distance / total_distance),
using the routing provider's total duration for the route.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

EARTH_RADIUS_MILES = 3958.7613


def haversine_miles(a: list[float], b: list[float]) -> float:
    """Great-circle distance in miles between [lat, lon] points a and b."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(h)))


def cumulative_distances(geometry: list[list[float]]) -> list[float]:
    """Cumulative distance (miles) at each vertex of the polyline."""
    cumulative = [0.0]
    for i in range(1, len(geometry)):
        cumulative.append(cumulative[-1] + haversine_miles(geometry[i - 1], geometry[i]))
    return cumulative


def point_at_distance(
    geometry: list[list[float]],
    cumulative: list[float],
    target_miles: float,
) -> list[float]:
    """Interpolate the [lat, lon] point at `target_miles` along the polyline."""
    if target_miles <= 0 or len(geometry) == 1:
        return list(geometry[0])
    total = cumulative[-1]
    if target_miles >= total:
        return list(geometry[-1])
    # Linear scan is fine: geometries are a few hundred points and
    # checkpoints per route are at most (distance/10 + 2).
    for i in range(1, len(cumulative)):
        if cumulative[i] >= target_miles:
            segment = cumulative[i] - cumulative[i - 1]
            fraction = 0.0 if segment == 0 else (target_miles - cumulative[i - 1]) / segment
            lat = geometry[i - 1][0] + (geometry[i][0] - geometry[i - 1][0]) * fraction
            lon = geometry[i - 1][1] + (geometry[i][1] - geometry[i - 1][1]) * fraction
            return [lat, lon]
    return list(geometry[-1])


def checkpoint_distances(total_miles: float, interval_miles: float) -> list[float]:
    """Checkpoint distances: 0, interval, 2×interval, …, plus the route end.

    The final checkpoint is exactly at the route end (it covers zero miles
    of segment itself but reports arrival weather at the destination).
    """
    if total_miles <= 0:
        return [0.0]
    distances = [0.0]
    step = float(interval_miles)
    current = step
    while current < total_miles - 1e-9:
        distances.append(round(current, 6))
        current += step
    distances.append(round(total_miles, 6))
    return distances


@dataclass(frozen=True)
class CheckpointLocation:
    distance_miles: float
    latitude: float
    longitude: float
    eta: datetime


def build_checkpoint_locations(
    geometry: list[list[float]],
    total_miles: float,
    duration_seconds: float,
    departure: datetime,
    interval_miles: float,
) -> list[CheckpointLocation]:
    """Place checkpoints along the geometry and compute each one's ETA."""
    cumulative = cumulative_distances(geometry)
    duration = timedelta(seconds=duration_seconds)
    locations: list[CheckpointLocation] = []
    for distance in checkpoint_distances(total_miles, interval_miles):
        lat, lon = point_at_distance(geometry, cumulative, distance)
        fraction = 0.0 if total_miles == 0 else distance / total_miles
        eta = departure + duration * fraction
        locations.append(
            CheckpointLocation(
                distance_miles=distance,
                latitude=lat,
                longitude=lon,
                eta=eta,
            )
        )
    return locations
