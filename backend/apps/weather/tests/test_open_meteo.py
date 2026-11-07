"""Open-Meteo provider + weather service tests (provider HTTP mocked)."""
from datetime import datetime, timezone
from unittest import mock

from django.test import SimpleTestCase

from apps.weather.providers import open_meteo
from apps.weather.services import weather_service

UTC = timezone.utc


def fake_open_meteo_payload():
    hours = ["2026-11-08T08:00", "2026-11-08T09:00", "2026-11-08T10:00"]
    block = {
        "hourly": {
            "time": hours,
            "wind_speed_10m": [10.0, 30.0, 60.0],
            "rain": [0.0, 0.30, 0.0],
            "snowfall": [0.0, 2.54, 0.0],  # cm: 2.54 cm == 1.0 inch
        }
    }
    return [block, block]


class OpenMeteoParsingTests(SimpleTestCase):
    @mock.patch("apps.weather.providers.open_meteo.get_json")
    def test_units_and_batching(self, mock_get):
        mock_get.return_value = fake_open_meteo_payload()
        forecasts = open_meteo.fetch_hourly_forecasts([(41.8, -87.6), (38.6, -90.2)])
        self.assertEqual(len(forecasts), 2)
        # Both coordinates went into ONE batched call.
        self.assertEqual(mock_get.call_count, 1)
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["latitude"], "41.8,38.6")
        self.assertEqual(params["wind_speed_unit"], "mph")
        self.assertEqual(params["precipitation_unit"], "inch")

        hour9 = forecasts[0][datetime(2026, 11, 8, 9, 0, tzinfo=UTC)]
        self.assertEqual(hour9.wind_mph, 30.0)
        self.assertEqual(hour9.rain_in_per_hr, 0.30)

    @mock.patch("apps.weather.providers.open_meteo.get_json")
    def test_snow_cm_to_inches(self, mock_get):
        mock_get.return_value = fake_open_meteo_payload()
        forecasts = open_meteo.fetch_hourly_forecasts([(41.8, -87.6), (38.6, -90.2)])
        hour9 = forecasts[0][datetime(2026, 11, 8, 9, 0, tzinfo=UTC)]
        self.assertAlmostEqual(hour9.snow_in_per_hr, 1.0, places=6)

    @mock.patch("apps.weather.providers.open_meteo.get_json")
    def test_missing_location_block_yields_empty(self, mock_get):
        mock_get.return_value = [{"hourly": {"time": [], "wind_speed_10m": [],
                                             "rain": [], "snowfall": []}}]
        forecasts = open_meteo.fetch_hourly_forecasts([(41.8, -87.6), (38.6, -90.2)])
        self.assertEqual(forecasts[1], {})


class WeatherAtEtaTests(SimpleTestCase):
    def setUp(self):
        block = {
            datetime(2026, 11, 8, 9, 0, tzinfo=UTC): open_meteo.HourlyForecast(30.0, 0.3, 1.0),
        }
        self.forecasts = [block]

    def test_rounds_to_nearest_hour(self):
        eta = datetime(2026, 11, 8, 9, 24, tzinfo=UTC)
        [wx] = weather_service.weather_at_eta(self.forecasts, [eta])
        self.assertTrue(wx.available)
        self.assertEqual(wx.wind_mph, 30.0)
        eta_late = datetime(2026, 11, 8, 8, 31, tzinfo=UTC)  # rounds up to 09:00
        [wx2] = weather_service.weather_at_eta(self.forecasts, [eta_late])
        self.assertTrue(wx2.available)

    def test_beyond_horizon_is_unavailable(self):
        eta = datetime(2026, 12, 25, 9, 0, tzinfo=UTC)
        [wx] = weather_service.weather_at_eta(self.forecasts, [eta])
        self.assertFalse(wx.available)
        self.assertIsNone(wx.wind_mph)

    def test_missing_measurement_is_unavailable(self):
        block = {datetime(2026, 11, 8, 9, 0, tzinfo=UTC):
                 open_meteo.HourlyForecast(None, 0.0, 0.0)}
        [wx] = weather_service.weather_at_eta(
            [block], [datetime(2026, 11, 8, 9, 0, tzinfo=UTC)]
        )
        self.assertFalse(wx.available)
