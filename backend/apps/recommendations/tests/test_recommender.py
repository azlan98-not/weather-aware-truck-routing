"""Unit tests for the lexicographic recommendation engine."""
from django.test import SimpleTestCase

from apps.recommendations.services.recommender import recommend


def make_route(route_id, severe, high, avg, duration, no_travel=False, reason=None):
    return {
        "id": route_id,
        "duration_minutes": duration,
        "has_no_travel": no_travel,
        "unsafe_reason": reason,
        "risk_summary": {
            "severe_miles": severe,
            "high_miles": high,
            "average_risk": avg,
        },
    }


class RecommendationPriorityTests(SimpleTestCase):
    def test_fewest_severe_wins_first(self):
        routes = [
            make_route(1, severe=5, high=0, avg=1.5, duration=100),
            make_route(2, severe=2, high=9, avg=2.5, duration=200),
        ]
        self.assertEqual(recommend(routes)["route_id"], 2)

    def test_high_breaks_severe_tie(self):
        routes = [
            make_route(1, severe=2, high=8, avg=1.5, duration=100),
            make_route(2, severe=2, high=3, avg=2.5, duration=200),
        ]
        self.assertEqual(recommend(routes)["route_id"], 2)

    def test_average_risk_breaks_high_tie(self):
        routes = [
            make_route(1, severe=2, high=3, avg=2.8, duration=100),
            make_route(2, severe=2, high=3, avg=1.9, duration=200),
        ]
        self.assertEqual(recommend(routes)["route_id"], 2)

    def test_duration_breaks_full_tie(self):
        routes = [
            make_route(1, severe=2, high=3, avg=2.0, duration=300),
            make_route(2, severe=2, high=3, avg=2.0, duration=250),
        ]
        self.assertEqual(recommend(routes)["route_id"], 2)

    def test_unknown_average_sorts_last_on_that_key(self):
        routes = [
            make_route(1, severe=0, high=0, avg=None, duration=100),
            make_route(2, severe=0, high=0, avg=4.0, duration=900),
        ]
        self.assertEqual(recommend(routes)["route_id"], 2)

    def test_comparison_includes_all_routes(self):
        routes = [make_route(1, 0, 0, 1.0, 100), make_route(2, 1, 0, 1.0, 100)]
        result = recommend(routes)
        self.assertEqual(len(result["comparison"]), 2)
        self.assertTrue(result["reasons"])


class NoTravelHandlingTests(SimpleTestCase):
    def test_clean_route_beats_no_travel_route_with_better_numbers(self):
        routes = [
            make_route(1, severe=0, high=0, avg=1.0, duration=100,
                       no_travel=True, reason="NO TRAVEL at mile 40"),
            make_route(2, severe=9, high=9, avg=3.5, duration=400),
        ]
        result = recommend(routes)
        self.assertEqual(result["route_id"], 2)
        self.assertTrue(any("NO TRAVEL" in r for r in result["reasons"]))

    def test_all_no_travel_picks_least_unsafe_with_warning(self):
        routes = [
            make_route(1, severe=10, high=0, avg=3.0, duration=100,
                       no_travel=True, reason="wind 60 mph"),
            make_route(2, severe=1, high=0, avg=3.0, duration=100,
                       no_travel=True, reason="wind 58 mph"),
        ]
        result = recommend(routes)
        self.assertEqual(result["route_id"], 2)
        self.assertTrue(any("WARNING" in r for r in result["reasons"]))
