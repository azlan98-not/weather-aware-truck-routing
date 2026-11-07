"""Unit tests for the centralized risk engine (no network, no Django DB)."""
from django.test import SimpleTestCase

from apps.risk.services import risk


class WindThresholdTests(SimpleTestCase):
    def test_boundaries(self):
        cases = [
            (0, risk.LOW), (24.9, risk.LOW),
            (25, risk.MODERATE), (34.9, risk.MODERATE),
            (35, risk.HIGH), (44.9, risk.HIGH),
            (45, risk.SEVERE), (54.9, risk.SEVERE),
            (55, risk.NO_TRAVEL), (80, risk.NO_TRAVEL),
        ]
        for value, expected in cases:
            with self.subTest(wind=value):
                self.assertEqual(risk.classify_wind(value), expected)


class RainThresholdTests(SimpleTestCase):
    def test_boundaries(self):
        cases = [
            (0.0, risk.LOW), (0.09, risk.LOW),
            (0.10, risk.MODERATE), (0.24, risk.MODERATE),
            (0.25, risk.HIGH), (0.49, risk.HIGH),
            (0.50, risk.SEVERE), (1.00, risk.SEVERE),   # SEVERE top is inclusive
            (1.01, risk.NO_TRAVEL), (2.5, risk.NO_TRAVEL),
        ]
        for value, expected in cases:
            with self.subTest(rain=value):
                self.assertEqual(risk.classify_rain(value), expected)


class SnowThresholdTests(SimpleTestCase):
    def test_boundaries(self):
        cases = [
            (0.0, risk.LOW), (0.49, risk.LOW),
            (0.5, risk.MODERATE), (0.99, risk.MODERATE),
            (1.0, risk.HIGH), (1.99, risk.HIGH),
            (2.0, risk.SEVERE), (3.0, risk.SEVERE),     # SEVERE top is inclusive
            (3.01, risk.NO_TRAVEL), (6.0, risk.NO_TRAVEL),
        ]
        for value, expected in cases:
            with self.subTest(snow=value):
                self.assertEqual(risk.classify_snow(value), expected)


class EvaluateCheckpointTests(SimpleTestCase):
    def test_highest_wins(self):
        # Wind LOW, rain HIGH, snow MODERATE -> HIGH overall.
        result = risk.evaluate_checkpoint(10, 0.30, 0.7, 20_000)
        self.assertEqual(result.level, risk.HIGH)
        self.assertEqual(result.score, 3)
        self.assertEqual(result.wind_level, risk.LOW)
        self.assertEqual(result.rain_level, risk.HIGH)
        self.assertEqual(result.snow_level, risk.MODERATE)
        self.assertTrue(result.weather_available)

    def test_missing_weather_is_unknown(self):
        for args in [(None, 0.0, 0.0), (10, None, 0.0), (10, 0.0, None)]:
            with self.subTest(args=args):
                result = risk.evaluate_checkpoint(*args, 20_000)
                self.assertEqual(result.level, risk.UNKNOWN)
                self.assertIsNone(result.score)
                self.assertFalse(result.weather_available)

    def test_load_rules(self):
        # Wind >= 55 -> NO_TRAVEL for ANY load (even light).
        self.assertEqual(
            risk.evaluate_checkpoint(55, 0.0, 0.0, 5_000).level, risk.NO_TRAVEL
        )
        self.assertEqual(
            risk.evaluate_checkpoint(70, 0.0, 0.0, 5_000).level, risk.NO_TRAVEL
        )
        # Wind 45-54 + load > 30,000 -> NO_TRAVEL; at exactly 30,000 stays SEVERE.
        self.assertEqual(
            risk.evaluate_checkpoint(50, 0.0, 0.0, 30_001).level, risk.NO_TRAVEL
        )
        self.assertEqual(
            risk.evaluate_checkpoint(50, 0.0, 0.0, 30_000).level, risk.SEVERE
        )
        self.assertTrue(
            risk.evaluate_checkpoint(50, 0.0, 0.0, 30_001).load_override_applied
        )
        # Wind 35-44 + load > 40,000 -> SEVERE; at exactly 40,000 stays HIGH.
        self.assertEqual(
            risk.evaluate_checkpoint(40, 0.0, 0.0, 40_001).level, risk.SEVERE
        )
        self.assertEqual(
            risk.evaluate_checkpoint(40, 0.0, 0.0, 40_000).level, risk.HIGH
        )
        # Load override never LOWERS a higher weather-driven risk.
        self.assertEqual(
            risk.evaluate_checkpoint(40, 1.5, 0.0, 45_000).level, risk.NO_TRAVEL
        )
        # Light load in moderate wind: no override.
        result = risk.evaluate_checkpoint(30, 0.0, 0.0, 45_000)
        self.assertEqual(result.level, risk.MODERATE)
        self.assertFalse(result.load_override_applied)
