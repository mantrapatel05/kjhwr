# -*- coding: utf-8 -*-
"""HTTP layer. THIN by design: validate request shape, call service, return.

Validation policy:
- unparsable params (bad date, bad HH:MM)        -> 422, string detail
- parseable but outside the January windows      -> 400, string detail
- bucket_hours outside 1..24                     -> 400
- unknown /api/* paths                           -> JSON 404 (catch-all LAST in router)

Metric floats are rounded to 3 decimals HERE, the serialisation point — full
precision flows through processing/metrics/service.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from . import config, schemas, service, timeutil

router = APIRouter(prefix="/api")

# forecast-versions window: [delivery 2026-01-02T00:00Z, 2026-02-02T00:00Z)
_TARGET_TIME_MIN = "2026-01-02T00:00:00Z"
_TARGET_TIME_MAX_EXCL = "2026-02-02T00:00:00Z"

_ROUND_KEYS = ("bias_mw", "mae_mw", "rmse_mw", "p90_abs_error_mw", "max_abs_error_mw", "coverage_pct")


def _round_payload(obj):
    """Round metric floats (any depth) at serialisation. Non-metrics untouched."""
    if isinstance(obj, dict):
        return {k: round(v, 3) if k in _ROUND_KEYS and isinstance(v, (int, float)) else _round_payload(v)
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_payload(item) for item in obj]
    return obj


def _decision_date_param(value: str, name: str):
    """Strict YYYY-MM-DD AND inside the January decision window, else 4xx string."""
    try:
        d = timeutil.parse_decision_date(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid {name}: {exc}") from exc
    if not (config.DECISION_FROM <= value <= config.DECISION_TO):
        raise HTTPException(
            status_code=400,
            detail=f"{name} outside the decision window ({config.DECISION_FROM} to {config.DECISION_TO})",
        )
    return d


def _cutoff_param(cutoff: str | None) -> str:
    """None -> config default; otherwise strictly HH:MM or 422 with a string detail."""
    if cutoff is None:
        return config.DEFAULT_CUTOFF
    try:
        timeutil.parse_time_of_day(cutoff)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid cutoff: {exc}") from exc
    return cutoff


def _iso_param(value: str, name: str):
    try:
        return timeutil.parse_utc(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid {name}: must be an ISO-Z timestamp ({exc})") from exc


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/config", response_model=schemas.ConfigResponse)
def get_config() -> dict:
    return {
        "decision_dates": {"from": config.DECISION_FROM, "to": config.DECISION_TO},
        "delivery_dates": {"from": config.DELIVERY_FROM, "to": config.DELIVERY_TO},
        "default_cutoff_utc": config.DEFAULT_CUTOFF,
        "cutoff_options_utc": config.CUTOFF_OPTIONS,
        "timezone_note": config.TIMEZONE_NOTE,
        "snapshot_fetched_at": service.fetched_at(),
    }


@router.get("/forecast-vs-actual", response_model=schemas.ForecastVsActualResponse)
def forecast_vs_actual(
    decision_date: str = Query(...),
    cutoff: str | None = Query(default=None),
) -> dict:
    _decision_date_param(decision_date, "decision_date")
    hhmm = _cutoff_param(cutoff)
    return _round_payload(service.day(decision_date, hhmm))


@router.get("/forecast-versions", response_model=schemas.VersionsResponse)
def forecast_versions(target_time: str = Query(...), cutoff: str = Query(...)) -> dict:
    target = _iso_param(target_time, "target_time")
    cutoff_dt = _iso_param(cutoff, "cutoff")
    if not (
        timeutil.parse_utc(_TARGET_TIME_MIN)
        <= target
        < timeutil.parse_utc(_TARGET_TIME_MAX_EXCL)
    ):
        raise HTTPException(
            status_code=400,
            detail=f"target_time outside the delivery window ({_TARGET_TIME_MIN} to {_TARGET_TIME_MAX_EXCL} exclusive)",
        )
    return _round_payload(service.versions(target, cutoff_dt))


@router.get("/metrics", response_model=schemas.DayMetrics)
def metrics_pooled(
    from_: str = Query(alias="from"),
    to: str = Query(...),
    cutoff: str | None = Query(default=None),
) -> dict:
    from_d = _decision_date_param(from_, "from")
    to_d = _decision_date_param(to, "to")
    if from_d > to_d:
        raise HTTPException(status_code=400, detail=f"from ({from_}) must be on or before to ({to})")
    hhmm = _cutoff_param(cutoff)
    return _round_payload(service.period_metrics(from_, to, hhmm))


@router.get("/metrics/daily", response_model=list[schemas.DailyMetrics])
def metrics_daily(cutoff: str | None = Query(default=None)) -> list[dict]:
    hhmm = _cutoff_param(cutoff)
    return _round_payload(service.daily_metrics(hhmm))


@router.get("/metrics/by-lead-time", response_model=list[schemas.LeadMetrics])
def metrics_by_lead_time(
    bucket_hours: int = Query(default=config.LEAD_BUCKET_HOURS_DEFAULT),
) -> list[dict]:
    if not (config.LEAD_BUCKET_HOURS_MIN <= bucket_hours <= config.LEAD_BUCKET_HOURS_MAX):
        raise HTTPException(
            status_code=400,
            detail=f"bucket_hours must be an integer from {config.LEAD_BUCKET_HOURS_MIN} to {config.LEAD_BUCKET_HOURS_MAX}",
        )
    return service.lead_time_buckets(bucket_hours)


# Catch-all LAST inside the router: unknown /api/* paths answer JSON "detail",
# never silently falling through to the static frontend mount.
@router.api_route("/{missing:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
def api_not_found(missing: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Not found"})
