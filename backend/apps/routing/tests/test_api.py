"""API tests for /api/v1/health/, /routes/analyze/, /routes/heatmap/.

All provider boundaries are mocked — the test suite never touches the
network.
"""
from datetime import datetime, timezone
from unittest import mock

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from apps.routing.providers import osrm
from apps.routing.providers.nominatim import GeocodedPlace, GeocodingError
from apps.weather.services.weather_service import CheckpointWeather
from common.http import ProviderError

UTC = timezone.utc
CHICAGO = GeocodedPlace("Chicago", "Chicago, Illinois, USA", 41.8781, -87.6298)
ST_LOUIS = GeocodedPlace("St Louis", "St. Louis, Missouri, USA", 38.6270, -90.1994)

GEOMETRY = [[41.8781, -87.6298], [40.5, -89.0], [38.6270, -90.1994]]
ROUTE = osrm.ProviderRoute(
    distance_miles=100.0, duration_seconds=7200.0,
    geometry=GEOMETRY, summary="I-55 S",
)
CALM = CheckpointWeather(10.0, 0.0, 0.0, True)

VALID_BODY = {
    "origin": "Chicago",
    "destination": "St Louis",
    "departure_datetime": "2026-11-08T08:00:00Z",
    "load_weight_lb": 35000,
    "checkpoint_interval_miles": 25,
}


def _geocode_side_effect(query):
    return CHICAGO if "Chicago" in query else ST_LOUIS


class HealthTests(SimpleTestCase):
    def test_health(self):
        response = APIClient().get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


@mock.patch("apps.routing.services.analysis.fetch_weather_for_points")
@mock.patch("apps.routing.services.analysis.osrm.fetch_routes")
@mock.patch("apps.routing.services.analysis.nominatim.geocode")
class AnalyzeApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def _mock_ok(self, mock_geocode, mock_routes, mock_weather):
        mock_geocode.side_effect = _geocode_side_effect
        mock_routes.return_value = ([ROUTE], False)
        mock_weather.side_effect = lambda points, etas: [CALM] * len(points)

    def test_analyze_response_structure(self, mock_geocode, mock_routes, mock_weather):
        self._mock_ok(mock_geocode, mock_routes, mock_weather)
        response = self.client.post("/api/v1/routes/analyze/", VALID_BODY, format="json")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("routes", payload)
        self.assertIn("recommendation", payload)
        self.assertIn("warnings", payload)
        # Only 1 mocked route -> explicit "only N routes" warning.
        self.assertTrue(any("Only 1" in w for w in payload["warnings"]))

        route = payload["routes"][0]
        for key in ("id", "summary", "distance_miles", "duration_minutes",
                    "departure_time", "arrival_time", "geometry", "checkpoints",
                    "risk_summary", "has_no_travel", "unsafe_reason"):
            self.assertIn(key, route)
        # 100-mile route at 25-mile interval: checkpoints at 0/25/50/75/100.
        self.assertEqual(len(route["checkpoints"]), 5)
        checkpoint = route["checkpoints"][0]
        for key in ("distance_miles", "latitude", "longitude", "eta", "wind_mph",
                    "rain_in_per_hr", "snow_in_per_hr", "risk_level", "risk_score",
                    "weather_available"):
            self.assertIn(key, checkpoint)
        self.assertEqual(checkpoint["risk_level"], "LOW")
        summary = route["risk_summary"]
        total = sum(summary[k] for k in (
            "low_miles", "moderate_miles", "high_miles",
            "severe_miles", "no_travel_miles", "unknown_miles"))
        self.assertAlmostEqual(total, 100.0, places=1)
        self.assertEqual(payload["recommendation"]["route_id"], route["id"])
        self.assertEqual(len(payload["recommendation"]["comparison"]), 1)

    def test_invalid_inputs(self, mock_geocode, mock_routes, mock_weather):
        self._mock_ok(mock_geocode, mock_routes, mock_weather)
        bad_bodies = [
            {**VALID_BODY, "load_weight_lb": 0},
            {**VALID_BODY, "load_weight_lb": -500},
            {**VALID_BODY, "checkpoint_interval_miles": 15},
            {**VALID_BODY, "departure_datetime": "not-a-date"},
            {**VALID_BODY, "origin": ""},
            {k: v for k, v in VALID_BODY.items() if k != "destination"},
        ]
        for body in bad_bodies:
            with self.subTest(body=body):
                response = self.client.post("/api/v1/routes/analyze/", body, format="json")
                self.assertEqual(response.status_code, 400)
                error = response.json()["error"]
                self.assertEqual(error["code"], "validation_error")
                self.assertTrue(error["fields"])

    def test_ungeocodable_origin(self, mock_geocode, mock_routes, mock_weather):
        mock_geocode.side_effect = GeocodingError("Location not found: 'zzz'")
        response = self.client.post("/api/v1/routes/analyze/", VALID_BODY, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "location_not_found")

    def test_provider_failure_is_graceful_502(self, mock_geocode, mock_routes, mock_weather):
        mock_geocode.side_effect = _geocode_side_effect
        mock_routes.side_effect = ProviderError("OSRM down")
        response = self.client.post("/api/v1/routes/analyze/", VALID_BODY, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"]["code"], "provider_unavailable")

    def test_no_travel_route_flagged(self, mock_geocode, mock_routes, mock_weather):
        mock_geocode.side_effect = _geocode_side_effect
        mock_routes.return_value = ([ROUTE], False)
        storm = CheckpointWeather(60.0, 0.0, 0.0, True)  # wind 60 -> NO_TRAVEL
        mock_weather.side_effect = lambda points, etas: [storm] * len(points)
        response = self.client.post("/api/v1/routes/analyze/", VALID_BODY, format="json")
        self.assertEqual(response.status_code, 200)
        route = response.json()["routes"][0]
        self.assertTrue(route["has_no_travel"])
        self.assertIn("NO TRAVEL", route["unsafe_reason"])
        self.assertEqual(route["risk_summary"]["highest_risk"], "NO_TRAVEL")


@mock.patch("apps.routing.services.heatmap.fetch_weather_for_points")
class HeatmapApiTests(SimpleTestCase):
    def test_heatmap(self, mock_weather):
        mock_weather.side_effect = lambda points, etas: [CALM] * len(points)
        body = {
            "geometry": GEOMETRY,
            "departure_datetime": "2026-11-08T08:00:00Z",
            "hour_offset": 6,
            "load_weight_lb": 35000,
            "checkpoint_interval_miles": 25,
            "duration_minutes": 120,
        }
        response = APIClient().post("/api/v1/routes/heatmap/", body, format="json")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["forecast_time"], "2026-11-08T14:00:00Z")
        self.assertTrue(payload["points"])
        self.assertEqual(payload["points"][0]["risk_level"], "LOW")

    def test_heatmap_rejects_offset_over_48(self, mock_weather):
        body = {
            "geometry": GEOMETRY,
            "departure_datetime": "2026-11-08T08:00:00Z",
            "hour_offset": 49,
            "load_weight_lb": 35000,
            "checkpoint_interval_miles": 25,
        }
        response = APIClient().post("/api/v1/routes/heatmap/", body, format="json")
        self.assertEqual(response.status_code, 400)
