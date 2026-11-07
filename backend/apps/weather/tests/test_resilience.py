"""Resilience tests: provider rate limits must not fail a whole analysis.

Regression coverage for the deployed 500s of 2026-11-07: the weather
provider answered HTTP 429 from the hosting platform's shared egress IP,
the error escaped the weather layer and the analyze endpoint returned 500.
"""
from datetime import datetime, timedelta, timezone
from unittest import mock

import requests
from django.test import SimpleTestCase

from apps.weather.services import weather_service
from common.http import ProviderError, get_json

UTC = timezone.utc


def _response(status_code, payload=None, headers=None):
    resp = mock.Mock(spec=requests.Response)
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = payload or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(
            f"{status_code}", response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


class RateLimitRetryTests(SimpleTestCase):
    @mock.patch("common.http.time.sleep")
    @mock.patch("common.http.requests.get")
    def test_429_is_retried_and_then_succeeds(self, mock_get, _mock_sleep):
        mock_get.side_effect = [
            _response(429, headers={"Retry-After": "1"}),
            _response(200, payload={"ok": True}),
        ]
        self.assertEqual(get_json("https://example.test/x"), {"ok": True})
        self.assertEqual(mock_get.call_count, 2)

    @mock.patch("common.http.time.sleep")
    @mock.patch("common.http.requests.get")
    def test_other_4xx_is_not_retried(self, mock_get, _mock_sleep):
        mock_get.side_effect = [_response(404)]
        with self.assertRaises(ProviderError):
            get_json("https://example.test/x")
        self.assertEqual(mock_get.call_count, 1)

    @mock.patch("common.http.time.sleep")
    @mock.patch("common.http.requests.get")
    def test_persistent_429_raises_provider_error(self, mock_get, _mock_sleep):
        mock_get.side_effect = [_response(429)] * 10
        with self.assertRaises(ProviderError):
            get_json("https://example.test/x", retries=2)
        self.assertEqual(mock_get.call_count, 3)  # initial + 2 retries


class WeatherDegradationTests(SimpleTestCase):
    @mock.patch(
        "apps.weather.services.weather_service.met_norway.fetch_hourly_forecasts",
        side_effect=ProviderError("backup down"),
    )
    @mock.patch(
        "apps.weather.services.weather_service.open_meteo.fetch_hourly_forecasts",
        side_effect=ProviderError("429 Too Many Requests"),
    )
    def test_provider_failure_marks_all_points_unknown(
        self, _mock_primary, _mock_backup
    ):
        points = [(41.8, -87.6), (38.6, -90.2)]
        etas = [datetime(2026, 11, 8, 9, 0, tzinfo=UTC)] * 2
        results = weather_service.fetch_weather_for_points(points, etas)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(not wx.available for wx in results))
        self.assertTrue(all(wx.wind_mph is None for wx in results))

    def test_forecast_days_needed_covers_late_eta(self):
        soon = datetime.now(UTC) + timedelta(days=1)
        self.assertLessEqual(
            weather_service._forecast_days_needed([soon]), 3
        )
        far = datetime.now(UTC) + timedelta(days=40)
        self.assertEqual(weather_service._forecast_days_needed([far]), 16)
