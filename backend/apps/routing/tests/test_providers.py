"""Nominatim + OSRM provider tests (HTTP layer mocked, no network)."""
from unittest import mock

from django.test import SimpleTestCase

from apps.routing.providers import nominatim, osrm
from common.http import ProviderError

CHICAGO = (41.8781, -87.6298)
ST_LOUIS = (38.6270, -90.1994)


def osrm_route(distance_m, duration_s, coords, summary="I-55 S"):
    return {
        "distance": distance_m,
        "duration": duration_s,
        "geometry": {"coordinates": [[lon, lat] for lat, lon in coords]},
        "legs": [{"summary": summary}],
    }


ROUTE_A = osrm_route(482_000, 16_200, [CHICAGO, (40.0, -89.0), ST_LOUIS])
ROUTE_B = osrm_route(500_000, 17_400, [CHICAGO, (40.2, -88.0), ST_LOUIS])
ROUTE_C = osrm_route(520_000, 18_000, [CHICAGO, (39.5, -90.5), ST_LOUIS])


class NominatimTests(SimpleTestCase):
    @mock.patch("apps.routing.providers.nominatim.get_json")
    def test_geocode_success(self, mock_get):
        mock_get.return_value = [
            {"lat": "41.8781", "lon": "-87.6298", "display_name": "Chicago, Illinois"}
        ]
        place = nominatim.geocode("Chicago")
        self.assertAlmostEqual(place.latitude, 41.8781)
        self.assertAlmostEqual(place.longitude, -87.6298)

    @mock.patch("apps.routing.providers.nominatim.get_json")
    def test_geocode_not_found(self, mock_get):
        mock_get.return_value = []
        with self.assertRaises(nominatim.GeocodingError):
            nominatim.geocode("zzz-not-a-place-zzz")


class OsrmTests(SimpleTestCase):
    @mock.patch("apps.routing.providers.osrm.get_json")
    def test_three_alternatives_no_fallback(self, mock_get):
        mock_get.return_value = {"code": "Ok", "routes": [ROUTE_A, ROUTE_B, ROUTE_C]}
        routes, fallback = osrm.fetch_routes(CHICAGO, ST_LOUIS)
        self.assertEqual(len(routes), 3)
        self.assertFalse(fallback)
        self.assertAlmostEqual(routes[0].distance_miles, 482_000 / 1609.344, places=1)
        # Geometry converted from GeoJSON [lon, lat] to [lat, lon].
        self.assertEqual(routes[0].geometry[0], [41.8781, -87.6298])

    @mock.patch("apps.routing.providers.osrm.get_json")
    def test_fallback_adds_detour_route(self, mock_get):
        # Primary returns only 2 (the known live behaviour); the first
        # detour-waypoint request supplies a genuine third route.
        mock_get.side_effect = [
            {"code": "Ok", "routes": [ROUTE_A, ROUTE_B]},
            {"code": "Ok", "routes": [ROUTE_C]},
        ]
        routes, fallback = osrm.fetch_routes(CHICAGO, ST_LOUIS)
        self.assertTrue(fallback)
        self.assertEqual(len(routes), 3)
        detour_call = mock_get.call_args_list[1]
        self.assertIn(";", detour_call.args[0])  # 3 waypoints in the URL

    @mock.patch("apps.routing.providers.osrm.get_json")
    def test_dedupe_identical_routes(self, mock_get):
        mock_get.side_effect = [
            {"code": "Ok", "routes": [ROUTE_A, ROUTE_A, ROUTE_B]},
            {"code": "Ok", "routes": [ROUTE_A]},       # detour duplicates A
            {"code": "Ok", "routes": [ROUTE_B]},       # detour duplicates B
        ]
        routes, _ = osrm.fetch_routes(CHICAGO, ST_LOUIS)
        signatures = [r.signature() for r in routes]
        self.assertEqual(len(signatures), len(set(signatures)))
        self.assertEqual(len(routes), 2)  # only 2 genuine routes exist in the mock

    @mock.patch("apps.routing.providers.osrm.get_json")
    def test_provider_failure_raises(self, mock_get):
        mock_get.side_effect = ProviderError("boom")
        with self.assertRaises(ProviderError):
            osrm.fetch_routes(CHICAGO, ST_LOUIS)

    @mock.patch("apps.routing.providers.osrm.get_json")
    def test_osrm_error_code_raises(self, mock_get):
        mock_get.return_value = {"code": "NoRoute", "message": "no route"}
        with self.assertRaises(ProviderError):
            osrm.fetch_routes(CHICAGO, ST_LOUIS)
