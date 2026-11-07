"""Geometry + ETA + risk-miles tests (pure math, no network)."""
from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from apps.routing.services.analysis import summarize_route_risk
from apps.routing.services.geometry import (
    build_checkpoint_locations,
    checkpoint_distances,
    cumulative_distances,
    haversine_miles,
    point_at_distance,
)

UTC = timezone.utc
# A straight east-west line: 1 degree of longitude at the equator ~ 69.09 miles.
LINE = [[0.0, 0.0], [0.0, 1.0], [0.0, 2.0]]


class HaversineTests(SimpleTestCase):
    def test_one_degree_longitude_at_equator(self):
        self.assertAlmostEqual(haversine_miles([0, 0], [0, 1]), 69.09, delta=0.1)


class CheckpointDistanceTests(SimpleTestCase):
    def test_includes_zero_steps_and_end(self):
        self.assertEqual(checkpoint_distances(100, 25), [0.0, 25.0, 50.0, 75.0, 100.0])

    def test_end_appended_when_not_on_step(self):
        self.assertEqual(checkpoint_distances(90, 25), [0.0, 25.0, 50.0, 75.0, 90.0])

    def test_interval_larger_than_route(self):
        self.assertEqual(checkpoint_distances(30, 50), [0.0, 30.0])


class InterpolationTests(SimpleTestCase):
    def test_midpoint_interpolation(self):
        cumulative = cumulative_distances(LINE)
        total = cumulative[-1]
        point = point_at_distance(LINE, cumulative, total / 2)
        self.assertAlmostEqual(point[0], 0.0, places=6)
        self.assertAlmostEqual(point[1], 1.0, places=4)

    def test_endpoints(self):
        cumulative = cumulative_distances(LINE)
        self.assertEqual(point_at_distance(LINE, cumulative, 0), [0.0, 0.0])
        self.assertEqual(point_at_distance(LINE, cumulative, 10_000), [0.0, 2.0])


class EtaTests(SimpleTestCase):
    def test_eta_proportional_to_distance(self):
        total = cumulative_distances(LINE)[-1]
        departure = datetime(2026, 11, 8, 8, 0, tzinfo=UTC)
        locations = build_checkpoint_locations(
            LINE, total, duration_seconds=7200, departure=departure, interval_miles=25
        )
        self.assertEqual(locations[0].eta, departure)
        self.assertAlmostEqual(
            (locations[-1].eta - (departure + timedelta(hours=2))).total_seconds(),
            0, delta=1,
        )
        # ETA increases monotonically with distance.
        etas = [loc.eta for loc in locations]
        self.assertEqual(etas, sorted(etas))
        mid = locations[len(locations) // 2]
        expected = departure + timedelta(seconds=7200 * mid.distance_miles / total)
        self.assertAlmostEqual((mid.eta - expected).total_seconds(), 0, delta=1)


def cp(distance, level, score):
    return {"distance_miles": distance, "risk_level": level, "risk_score": score}


class RiskMilesTests(SimpleTestCase):
    def test_risk_miles_reconcile_with_total(self):
        checkpoints = [
            cp(0, "LOW", 1), cp(25, "HIGH", 3), cp(50, "UNKNOWN", None),
            cp(75, "SEVERE", 4), cp(100, "LOW", 1),
        ]
        summary = summarize_route_risk(checkpoints, total_miles=100)
        total = sum(
            summary[k] for k in (
                "low_miles", "moderate_miles", "high_miles",
                "severe_miles", "no_travel_miles", "unknown_miles",
            )
        )
        self.assertAlmostEqual(total, 100.0, places=3)
        self.assertEqual(summary["low_miles"], 25.0)       # 0->25; final cp covers 0
        self.assertEqual(summary["high_miles"], 25.0)      # 25->50
        self.assertEqual(summary["unknown_miles"], 25.0)   # 50->75
        self.assertEqual(summary["severe_miles"], 25.0)    # 75->100

    def test_average_risk_is_distance_weighted_over_known_miles(self):
        checkpoints = [cp(0, "LOW", 1), cp(90, "SEVERE", 4), cp(100, "LOW", 1)]
        summary = summarize_route_risk(checkpoints, total_miles=100)
        # 90 mi at score 1 + 10 mi at score 4 = (90 + 40) / 100 = 1.3
        self.assertAlmostEqual(summary["average_risk"], 1.3, places=3)
        self.assertEqual(summary["highest_risk"], "SEVERE")

    def test_risky_checkpoint_count(self):
        checkpoints = [
            cp(0, "LOW", 1), cp(25, "HIGH", 3),
            cp(50, "NO_TRAVEL", 5), cp(75, "MODERATE", 2),
        ]
        summary = summarize_route_risk(checkpoints, total_miles=75)
        self.assertEqual(summary["risky_checkpoint_count"], 2)
        self.assertEqual(summary["highest_risk"], "NO_TRAVEL")

    def test_all_unknown_average_is_none(self):
        checkpoints = [cp(0, "UNKNOWN", None), cp(50, "UNKNOWN", None)]
        summary = summarize_route_risk(checkpoints, total_miles=50)
        self.assertIsNone(summary["average_risk"])
        self.assertIsNone(summary["highest_risk"])
        self.assertEqual(summary["unknown_miles"], 50.0)
