# -*- coding: utf-8 -*-
"""Response schemas: the EXACT field names the React frontend depends on.

Every response key set must match the contract exactly — no extra, no missing keys.
MW values are numbers or null (missing is missing, never 0). Metric floats are
rounded to 3 decimals AT SERIALISATION ONLY, via field serializers — full precision
flows through processing/metrics/service.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_serializer

_MW_FIELDS = ("bias_mw", "mae_mw", "rmse_mw", "p90_abs_error_mw", "max_abs_error_mw")


def _round3(v):
    return None if v is None else round(float(v), 3)


class TimeRange(BaseModel):
    """{"from": "...", "to": "..."} — 'from' is a Python keyword, aliased."""

    model_config = ConfigDict(populate_by_name=True)
    from_: str = Field(alias="from")
    to: str


class ConfigResponse(BaseModel):
    decision_dates: TimeRange
    delivery_dates: TimeRange
    default_cutoff_utc: str
    cutoff_options_utc: list[str]
    timezone_note: str
    snapshot_fetched_at: str | None


class DayMetrics(BaseModel):
    """Full pool: /api/metrics and the metrics object of /api/forecast-vs-actual."""

    @field_serializer(*_MW_FIELDS, "coverage_pct")
    def _round(self, v):
        return _round3(v)

    n: int
    expected: int
    coverage_pct: float | None
    bias_mw: float | None
    mae_mw: float | None
    rmse_mw: float | None
    p90_abs_error_mw: float | None
    max_abs_error_mw: float | None


class DailyMetrics(BaseModel):
    """One decision date: /api/metrics/daily row (no 'expected', no 'max')."""

    @field_serializer("bias_mw", "mae_mw", "rmse_mw", "p90_abs_error_mw", "coverage_pct")
    def _round(self, v):
        return _round3(v)

    decision_date: str
    delivery_day: str
    n: int
    bias_mw: float | None
    mae_mw: float | None
    rmse_mw: float | None
    p90_abs_error_mw: float | None
    coverage_pct: float | None


class LeadMetrics(BaseModel):
    """One lead-time bucket: /api/metrics/by-lead-time row."""

    @field_serializer("bias_mw", "mae_mw", "rmse_mw")
    def _round(self, v):
        return _round3(v)

    bucket_start_h: int
    bucket_end_h: int | None  # None only for the final, open-ended bucket
    n: int
    bias_mw: float | None
    mae_mw: float | None
    rmse_mw: float | None


class Point(BaseModel):
    """One delivery interval: forecast as known at the cutoff, actual, error."""

    start_time: str
    forecast_mw: float | None
    actual_mw: float | None
    publish_time: str | None
    lead_time_h: float | None
    error_mw: float | None
    matched: bool


class ActualOnly(BaseModel):
    """Window actual with NO chosen forecast (e.g. :30 half-hours)."""

    start_time: str
    actual_mw: float | None


class ForecastVsActualResponse(BaseModel):
    decision_date: str
    cutoff_utc: str
    delivery_day: str
    expected_points: int
    matched_points: int
    points: list[Point]
    actuals_only: list[ActualOnly]
    metrics: DayMetrics


class VersionEntry(BaseModel):
    publish_time: str
    forecast_mw: float | None
    lead_time_h: float | None
    available_at_cutoff: bool
    selected: bool


class VersionsResponse(BaseModel):
    target_time: str
    cutoff_utc: str
    versions: list[VersionEntry]
