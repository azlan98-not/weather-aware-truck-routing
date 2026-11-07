"""HTTP layer only: parse, validate, delegate to services, respond.

Consistent error shape for every failure:
    {"error": {"code": <str>, "message": <str>, "fields": {<field>: [msgs]}}}
Internal exception details are logged, never exposed to clients.
"""
from __future__ import annotations

import logging
from datetime import timezone as dt_timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.routing.serializers import (
    AnalyzeRequestSerializer,
    HeatmapRequestSerializer,
)
from apps.routing.services.analysis import AnalysisError, analyze_trip
from apps.routing.services.heatmap import build_heatmap
from common.http import ProviderError

logger = logging.getLogger("apps.routing.views")


def _error_response(code: str, message: str, http_status: int, fields: dict | None = None) -> Response:
    return Response(
        {"error": {"code": code, "message": message, "fields": fields or {}}},
        status=http_status,
    )


def _validation_error_response(serializer) -> Response:
    fields = {
        field: [str(msg) for msg in messages]
        for field, messages in serializer.errors.items()
    }
    return _error_response(
        "validation_error",
        "One or more fields are invalid.",
        status.HTTP_400_BAD_REQUEST,
        fields=fields,
    )


def _as_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=dt_timezone.utc)
    return dt.astimezone(dt_timezone.utc)


@api_view(["GET"])
def health(request: Request) -> Response:
    return Response({"status": "ok"})


@api_view(["POST"])
def analyze(request: Request) -> Response:
    serializer = AnalyzeRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_error_response(serializer)
    data = serializer.validated_data
    try:
        payload = analyze_trip(
            origin_query=data["origin"],
            destination_query=data["destination"],
            departure=_as_utc(data["departure_datetime"]),
            load_weight_lb=data["load_weight_lb"],
            interval_miles=data["checkpoint_interval_miles"],
        )
    except AnalysisError as exc:
        return _error_response(exc.code, exc.message, exc.status)
    except Exception:  # pragma: no cover - defensive catch-all
        logger.exception("unexpected analysis failure")
        return _error_response(
            "internal_error",
            "Something went wrong while analyzing this trip. Please try again.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return Response(payload)


@api_view(["POST"])
def heatmap(request: Request) -> Response:
    serializer = HeatmapRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_error_response(serializer)
    data = serializer.validated_data
    try:
        payload = build_heatmap(
            geometry=[[float(p[0]), float(p[1])] for p in data["geometry"]],
            departure=_as_utc(data["departure_datetime"]),
            hour_offset=data["hour_offset"],
            load_weight_lb=data["load_weight_lb"],
            interval_miles=data["checkpoint_interval_miles"],
            duration_minutes=data.get("duration_minutes"),
        )
    except ProviderError:
        logger.exception("heatmap provider failure")
        return _error_response(
            "provider_unavailable",
            "Weather provider is unavailable. Please try again.",
            status.HTTP_502_BAD_GATEWAY,
        )
    except Exception:  # pragma: no cover - defensive catch-all
        logger.exception("unexpected heatmap failure")
        return _error_response(
            "internal_error",
            "Something went wrong while building the heatmap. Please try again.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return Response(payload)
