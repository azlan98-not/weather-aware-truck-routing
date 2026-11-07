"""Centralized weather-risk classification engine.

Pure functions with no Django or I/O dependencies, so the module is
independently unit-testable (see apps/risk/tests/test_risk.py). This is the
ONLY place risk thresholds live — views, serializers and the frontend never
re-implement them.

Numeric scale (used for distance-weighted averaging):
    LOW = 1, MODERATE = 2, HIGH = 3, SEVERE = 4, NO_TRAVEL = 5.

Boundary handling (exact, per the assessment brief):
    - General rule: a band's lower bound is INCLUSIVE and its upper bound is
      EXCLUSIVE — a value belongs to the first band whose range contains it.
    - Wind bands are written as whole-mph ranges in the brief (25–34, 35–44,
      45–54), so they are evaluated as >= lower and < lower+10
      (e.g. 34.9 mph is MODERATE, 35.0 mph is HIGH).
    - Rain and snow SEVERE bands are written with closed tops in the brief
      ("0.50–1.00" severe, ">1.00" no-travel; "2.0–3.0" severe, ">3.0"
      no-travel), so 1.00 in/hr rain and 3.0 in/hr snow are SEVERE, and only
      values strictly above them are NO_TRAVEL.

Load-based overrides (applied AFTER the weather-only classification):
    - Wind >= 55 mph            -> NO_TRAVEL for every load.
    - Wind 45–54 mph AND load > 30,000 lb -> NO_TRAVEL.
    - Wind 35–44 mph AND load > 40,000 lb -> at least SEVERE.

Missing weather: if any of wind/rain/snow is missing (None), the checkpoint
risk is UNKNOWN — missing data is never treated as safe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

LOW = "LOW"
MODERATE = "MODERATE"
HIGH = "HIGH"
SEVERE = "SEVERE"
NO_TRAVEL = "NO_TRAVEL"
UNKNOWN = "UNKNOWN"

RISK_SCORES: dict[str, int] = {
    LOW: 1,
    MODERATE: 2,
    HIGH: 3,
    SEVERE: 4,
    NO_TRAVEL: 5,
}
SCORE_LABELS: dict[int, str] = {score: label for label, score in RISK_SCORES.items()}

# Load thresholds (pounds) from the brief.
HEAVY_LOAD_FOR_SEVERE_WIND_LB = 30_000   # wind 45–54 mph + load above this -> NO_TRAVEL
HEAVY_LOAD_FOR_HIGH_WIND_LB = 40_000     # wind 35–44 mph + load above this -> SEVERE


def classify_wind(wind_mph: float) -> str:
    """Wind risk: <25 LOW; 25–34 MODERATE; 35–44 HIGH; 45–54 SEVERE; >=55 NO_TRAVEL."""
    if wind_mph < 25:
        return LOW
    if wind_mph < 35:
        return MODERATE
    if wind_mph < 45:
        return HIGH
    if wind_mph < 55:
        return SEVERE
    return NO_TRAVEL


def classify_rain(rain_in_per_hr: float) -> str:
    """Rain risk: <0.10 LOW; 0.10–<0.25 MODERATE; 0.25–<0.50 HIGH;
    0.50–1.00 (inclusive) SEVERE; >1.00 NO_TRAVEL."""
    if rain_in_per_hr < 0.10:
        return LOW
    if rain_in_per_hr < 0.25:
        return MODERATE
    if rain_in_per_hr < 0.50:
        return HIGH
    if rain_in_per_hr <= 1.00:
        return SEVERE
    return NO_TRAVEL


def classify_snow(snow_in_per_hr: float) -> str:
    """Snow risk: <0.5 LOW; 0.5–<1.0 MODERATE; 1.0–<2.0 HIGH;
    2.0–3.0 (inclusive) SEVERE; >3.0 NO_TRAVEL."""
    if snow_in_per_hr < 0.5:
        return LOW
    if snow_in_per_hr < 1.0:
        return MODERATE
    if snow_in_per_hr < 2.0:
        return HIGH
    if snow_in_per_hr <= 3.0:
        return SEVERE
    return NO_TRAVEL


@dataclass(frozen=True)
class CheckpointRisk:
    """Result of evaluating one checkpoint."""

    level: str                       # LOW..NO_TRAVEL, or UNKNOWN
    score: Optional[int]             # 1..5, or None when UNKNOWN
    wind_level: Optional[str]
    rain_level: Optional[str]
    snow_level: Optional[str]
    load_override_applied: bool
    weather_available: bool


def evaluate_checkpoint(
    wind_mph: Optional[float],
    rain_in_per_hr: Optional[float],
    snow_in_per_hr: Optional[float],
    load_weight_lb: float,
) -> CheckpointRisk:
    """Classify one checkpoint from its weather at ETA plus the truck load.

    Wind, rain and snow are evaluated independently; the checkpoint risk is
    the highest of the three, then load-based overrides are applied.
    Any missing measurement -> UNKNOWN (never treated as safe).
    """
    if wind_mph is None or rain_in_per_hr is None or snow_in_per_hr is None:
        return CheckpointRisk(
            level=UNKNOWN,
            score=None,
            wind_level=None,
            rain_level=None,
            snow_level=None,
            load_override_applied=False,
            weather_available=False,
        )

    wind_level = classify_wind(wind_mph)
    rain_level = classify_rain(rain_in_per_hr)
    snow_level = classify_snow(snow_in_per_hr)

    score = max(
        RISK_SCORES[wind_level], RISK_SCORES[rain_level], RISK_SCORES[snow_level]
    )

    # Load-based overrides (wind-driven, per the brief).
    override = False
    if wind_mph >= 55:
        # NO_TRAVEL for every load (also implied by classify_wind).
        if score < RISK_SCORES[NO_TRAVEL]:
            score = RISK_SCORES[NO_TRAVEL]
            override = True
    elif 45 <= wind_mph < 55 and load_weight_lb > HEAVY_LOAD_FOR_SEVERE_WIND_LB:
        if score < RISK_SCORES[NO_TRAVEL]:
            score = RISK_SCORES[NO_TRAVEL]
            override = True
    elif 35 <= wind_mph < 45 and load_weight_lb > HEAVY_LOAD_FOR_HIGH_WIND_LB:
        if score < RISK_SCORES[SEVERE]:
            score = RISK_SCORES[SEVERE]
            override = True

    return CheckpointRisk(
        level=SCORE_LABELS[score],
        score=score,
        wind_level=wind_level,
        rain_level=rain_level,
        snow_level=snow_level,
        load_override_applied=override,
        weather_available=True,
    )
