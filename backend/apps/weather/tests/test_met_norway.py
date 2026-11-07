"""Backup provider tests: MET Norway parsing + service-level fallback.

The backup exists for the failure seen on the hosted backend on
2026-11-07: Open-Meteo rate-limited the platform's shared egress IP, so
every hosted checkpoint degraded to UNKNOWN. When the primary provider
raises, the weather service must serve the same checkpoints from MET
Norway instead; only if BOTH fail may points degrade to UNAVAILABLE.
"""
from datetime import datetime, timezone
from unittest import mock

from django.test import SimpleTestCase

from apps.weather.providers import met_norway
from apps.weather.providers.open_meteo import HourlyForecast
from apps.weather.services import weather_service
from common.http import ProviderError

UTC = timezone.utc


def _entry(time, wind_ms, block_name=None, amount=None, symbol=""):
    data = {"instant": {"details": {"wind_speed": wind_ms}}}
    if block_name:
        data[block_name] = {
            "summary": {"symbol_code": symbol},
            "details": {"precipitation_amount": amount},
        }
    return {"time": time, "data": data}


PAYLOAD = {
    "properties": {
        "timeseries": [
            # Rain hour: 2.54 mm -> exactly 0.10 in/hr; wind 10 m/s.
            _entry("2026-11-08T08:00:00Z", 10.0, "next_1_hours", 2.54, "rain"),
            # Snow hour: 1.27 mm water -> 0.50 in/hr at the 10:1 ratio.
            _entry(
                "2026-11-08T09:00:00Z", 5.0, "next_1_hours", 1.27, "snow"
            ),
            # 6-hour block only: 6 mm over 6 h -> 1 mm/hr of rain.
            _entry(
                "2026-11-08T10:00:00Z", 2.5, "next_6_hours", 6.0, "lightrain"
            ),
        ]
    }
}


class MetNorwayParsingTests(SimpleTestCase):
    def test_units_and_rain_snow_split(self):
        forecasts = met_norway._location_forecasts(PAYLOAD)
        rain_hour = forecasts[datetime(2026, 11, 8, 8, tzinfo=UTC)]
        self.assertAlmostEqual(rain_hour.wind_mph, 22.3694, places=3)
        self.assertAlmostEqual(rain_hour.rain_in_per_hr, 0.10, places=6)
        self.assertEqual(rain_hour.snow_in_per_hr, 0.0)

        snow_hour = forecasts[datetime(2026, 11, 8, 9, tzinfo=UTC)]
        self.assertEqual(snow_hour.rain_in_per_hr, 0.0)
        self.assertAlmostEqual(snow_hour.snow_in_per_hr, 0.50, places=6)

        six_hour = forecasts[datetime(2026, 11, 8, 10, tzinfo=UTC)]
        self.assertAlmostEqual(
            six_hour.rain_in_per_hr, 1.0 / 25.4, places=6
        )

    @mock.patch("apps.weather.providers.met_norway.get_json")
    def test_sends_identifying_user_agent(self, mock_get_json):
        mock_get_json.return_value = PAYLOAD
        met_norway._fetch_one((41.8781, -87.6298))
        headers = mock_get_json.call_args.kwargs["headers"]
        self.assertIn("weather-aware-truck-routing", headers["User-Agent"])

    @mock.patch("apps.weather.providers.met_norway.get_json")
    def test_one_failed_point_degrades_but_others_survive(self, mock_get):
        mock_get.side_effect = [ProviderError("boom"), PAYLOAD]
        results = met_norway.fetch_hourly_forecasts(
            [(0.0, 0.0), (41.8781, -87.6298)]
        )
        self.assertEqual(results[0], {})
        self.assertTrue(results[1])

    @mock.patch(
        "apps.weather.providers.met_norway.get_json",
        side_effect=ProviderError("down"),
    )
    def test_all_points_failing_raises(self, _mock_get):
        with self.assertRaises(ProviderError):
            met_norway.fetch_hourly_forecasts([(41.8, -87.6)])


class FallbackEngagementTests(SimpleTestCase):
    @mock.patch(
        "apps.weather.services.weather_service.met_norway.fetch_hourly_forecasts"
    )
    @mock.patch(
        "apps.weather.services.weather_service.open_meteo.fetch_hourly_forecasts",
        side_effect=ProviderError("429 Too Many Requests"),
    )
    def test_backup_serves_points_when_primary_fails(
        self, _mock_primary, mock_backup
    ):
        hour = datetime(2026, 11, 8, 8, tzinfo=UTC)
        mock_backup.return_value = [
            {hour: HourlyForecast(12.0, 0.05, 0.0)}
        ]
        results = weather_service.fetch_weather_for_points(
            [(41.8, -87.6)], [hour]
        )
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].available)
        self.assertEqual(results[0].wind_mph, 12.0)
