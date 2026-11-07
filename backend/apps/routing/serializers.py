"""Input validation for the routing API.

Every field is validated server-side; DRF field errors are converted by the
views into the consistent error shape:
    {"error": {"code": "validation_error", "message": ..., "fields": {...}}}
"""
from __future__ import annotations

from rest_framework import serializers

ALLOWED_INTERVALS = (10, 25, 50)


class AnalyzeRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(min_length=2, max_length=200, trim_whitespace=True)
    destination = serializers.CharField(min_length=2, max_length=200, trim_whitespace=True)
    departure_datetime = serializers.DateTimeField()
    load_weight_lb = serializers.FloatField(min_value=0.0001)
    checkpoint_interval_miles = serializers.IntegerField()

    def validate_load_weight_lb(self, value: float) -> float:
        if value <= 0:
            raise serializers.ValidationError("Load weight must be positive.")
        if value > 200_000:
            raise serializers.ValidationError("Load weight is unrealistically large.")
        return value

    def validate_checkpoint_interval_miles(self, value: int) -> int:
        if value not in ALLOWED_INTERVALS:
            raise serializers.ValidationError(
                f"Checkpoint interval must be one of {list(ALLOWED_INTERVALS)} miles."
            )
        return value


class HeatmapRequestSerializer(serializers.Serializer):
    geometry = serializers.ListField(
        child=serializers.ListField(
            child=serializers.FloatField(), min_length=2, max_length=2
        ),
        min_length=2,
    )
    departure_datetime = serializers.DateTimeField()
    hour_offset = serializers.FloatField(min_value=0, max_value=48)
    load_weight_lb = serializers.FloatField(min_value=0.0001)
    checkpoint_interval_miles = serializers.IntegerField()
    # Optional: the selected route's provider duration, so travel-time-to-
    # point uses the same ETA method as the analysis. See services/heatmap.py.
    duration_minutes = serializers.FloatField(
        min_value=0.0001, required=False, allow_null=True, default=None
    )

    def validate_load_weight_lb(self, value: float) -> float:
        if value <= 0:
            raise serializers.ValidationError("Load weight must be positive.")
        return value

    def validate_checkpoint_interval_miles(self, value: int) -> int:
        if value not in ALLOWED_INTERVALS:
            raise serializers.ValidationError(
                f"Checkpoint interval must be one of {list(ALLOWED_INTERVALS)} miles."
            )
        return value
