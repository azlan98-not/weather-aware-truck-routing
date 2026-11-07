"""Deterministic route recommendation engine.

Priority (exact, from the brief — lexicographic, NOT a weighted score):
    1. Fewest Severe miles
    2. Fewest High miles
    3. Lowest average risk (distance-weighted)
    4. Shortest travel time

NO_TRAVEL handling (documented decision): a route containing any NO_TRAVEL
checkpoint is unsafe. Such routes are ranked BELOW every route without
no-travel segments, regardless of the lexicographic keys. Only when every
candidate route contains a no-travel segment is the lexicographic order
applied among them, and the recommendation then carries an explicit unsafe
warning — an unsafe route is never recommended silently.

The input is a list of plain route-summary dicts (produced by the routing
analysis service); this module has no Django or provider dependencies.
"""
from __future__ import annotations

from typing import Any

# Sort sentinel for routes whose average risk is entirely unknown: they sort
# after any route with a measurable average risk on that key.
_UNKNOWN_AVG = float("inf")


def _sort_key(route: dict[str, Any]) -> tuple:
    summary = route["risk_summary"]
    average = summary["average_risk"]
    return (
        1 if route.get("has_no_travel") else 0,   # unsafe routes last
        summary["severe_miles"],
        summary["high_miles"],
        _UNKNOWN_AVG if average is None else average,
        route["duration_minutes"],
    )


def _fmt(value: float | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def recommend(routes: list[dict[str, Any]]) -> dict[str, Any]:
    """Return {route_id, reasons, comparison} for the best route.

    Each route dict must carry: id, duration_minutes, has_no_travel,
    unsafe_reason (str | None), risk_summary {severe_miles, high_miles,
    average_risk, ...}.
    """
    if not routes:
        raise ValueError("recommend() requires at least one route")

    ranked = sorted(routes, key=_sort_key)
    best = ranked[0]
    best_summary = best["risk_summary"]

    reasons: list[str] = []
    if best.get("has_no_travel"):
        reasons.append(
            "WARNING: every available route contains a NO TRAVEL segment. "
            f"This route was selected as the least unsafe option: "
            f"{best.get('unsafe_reason') or 'no-travel conditions present'}."
        )
    else:
        reasons.append(
            "Selected because it has no NO TRAVEL segments and wins the "
            "priority order: fewest severe miles, then fewest high miles, "
            "then lowest average risk, then shortest travel time."
        )
    reasons.append(
        f"Severe miles: {_fmt(best_summary['severe_miles'])}; "
        f"High miles: {_fmt(best_summary['high_miles'])}; "
        f"Average risk: {_fmt(best_summary['average_risk'], 2)}; "
        f"Travel time: {_fmt(best['duration_minutes'], 0)} min."
    )
    for other in ranked[1:]:
        o = other["risk_summary"]
        if other.get("has_no_travel"):
            reasons.append(
                f"Route {other['id']} was ranked lower because it contains a "
                f"NO TRAVEL segment ({other.get('unsafe_reason') or 'unsafe conditions'})."
            )
        else:
            reasons.append(
                f"Route {other['id']} ranked lower on the priority order "
                f"(severe {_fmt(o['severe_miles'])} mi, high {_fmt(o['high_miles'])} mi, "
                f"avg risk {_fmt(o['average_risk'], 2)}, {_fmt(other['duration_minutes'], 0)} min)."
            )

    comparison = [
        {
            "route_id": route["id"],
            "severe_miles": route["risk_summary"]["severe_miles"],
            "high_miles": route["risk_summary"]["high_miles"],
            "average_risk": route["risk_summary"]["average_risk"],
            "duration_minutes": route["duration_minutes"],
        }
        for route in routes
    ]

    return {
        "route_id": best["id"],
        "reasons": reasons,
        "comparison": comparison,
    }
