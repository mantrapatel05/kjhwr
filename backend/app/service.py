# -*- coding: utf-8 -*-
"""Service layer: the ONE orchestration point.

routes.py stays thin; ALL orchestration lives here. The snapshot is loaded ONCE
per process (service.load at startup) and kept in memory for its lifetime — the
deployed app never reads the network or data/raw/ at runtime.

Caching: computed days are cached per (decision_date, cutoff) — 31 x 5 tiny,
deterministic combinations an unbounded cache handles correctly. Actuals and
forecast versions are indexed by start_time at load.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache

from . import config, data_store, metrics, processing, timeutil

_FORECASTS: list | None = None
_ACTUALS: dict = {}                # {start_time str ISO-Z: generation} (data_store shape)
_ACTUALS_BY_DT: dict = {}          # same, keyed by parsed datetime (lead-time needs it)
_FORECASTS_BY_START: dict = {}     # {start_time datetime: [version records]}
_META: dict = {}

# Lead-time scope decision: only versions published inside January 2026, for
# startTime inside the January delivery span.
_LEAD_PUB_START = timeutil.parse_utc("2026-01-01T00:00:00Z")
_LEAD_PUB_END_EXCL = timeutil.parse_utc("2026-02-01T00:00:00Z")
_LEAD_START_START = timeutil.parse_utc("2026-01-02T00:00:00Z")
_LEAD_START_END_EXCL = timeutil.parse_utc("2026-02-02T00:00:00Z")


def load() -> None:
    """Load and validate the snapshot ONCE. Fail fast on missing/malformed files."""
    global _FORECASTS, _ACTUALS, _ACTUALS_BY_DT, _FORECASTS_BY_START, _META
    snapshot = data_store.load_snapshot()
    _META = snapshot["meta"]
    _FORECASTS = snapshot["forecasts"]
    _ACTUALS = data_store.actuals_by_start(snapshot)
    _ACTUALS_BY_DT = {timeutil.parse_utc(k): v for k, v in _ACTUALS.items()}
    _FORECASTS_BY_START = {}
    for row in _FORECASTS:
        _FORECASTS_BY_START.setdefault(timeutil.parse_utc(row["start_time"]), []).append(row)
    _day_cache.cache_clear()  # a reload invalidates every cached day


def loaded() -> bool:
    return _FORECASTS is not None


def fetched_at() -> str | None:
    return _META.get("fetched_at_utc")


def _ensure_loaded() -> None:
    if _FORECASTS is None:
        load()


@lru_cache(maxsize=None)
def _day_cache(decision_date: str, cutoff: str):
    """True cache; key stays plain strings (decision_date, cutoff)."""
    return processing.as_of_series(decision_date, cutoff, _FORECASTS, _ACTUALS)


def day(decision_date: str, cutoff: str | None = None) -> dict:
    """/api/forecast-vs-actual payload for one decision (config default cutoff if None)."""
    _ensure_loaded()
    return _day_cache(decision_date, cutoff or config.DEFAULT_CUTOFF)


def period_metrics(from_date: str, to_date: str, cutoff: str | None = None) -> dict:
    """/api/metrics: metrics POOLED over all matched points of decision dates in
    [from_date, to_date] — NOT an average of daily metrics."""
    _ensure_loaded()
    cursor = timeutil.parse_decision_date(from_date)
    end = timeutil.parse_decision_date(to_date)
    errors: list[float] = []
    expected_total = 0
    matched_total = 0
    while cursor <= end:
        day_data = _day_cache(cursor.isoformat(), cutoff or config.DEFAULT_CUTOFF)
        errors.extend(p["error_mw"] for p in day_data["points"] if p["error_mw"] is not None)
        expected_total += day_data["expected_points"]
        matched_total += day_data["matched_points"]
        cursor += timedelta(days=1)
    pooled = metrics.compute_metrics(errors)
    pooled["expected"] = expected_total
    pooled["coverage_pct"] = (matched_total / expected_total) * 100.0 if expected_total else 0.0
    return pooled


def daily_metrics(cutoff: str | None = None) -> list[dict]:
    """/api/metrics/daily: one row per decision date in January 2026, cutoff applied."""
    _ensure_loaded()
    rows = []
    cursor = timeutil.parse_decision_date(config.DECISION_FROM)
    end = timeutil.parse_decision_date(config.DECISION_TO)
    while cursor <= end:
        day_data = _day_cache(cursor.isoformat(), cutoff or config.DEFAULT_CUTOFF)
        m = day_data["metrics"]
        rows.append(
            {
                "decision_date": day_data["decision_date"],
                "delivery_day": day_data["delivery_day"],
                "n": m["n"],
                "bias_mw": m["bias_mw"],
                "mae_mw": m["mae_mw"],
                "rmse_mw": m["rmse_mw"],
                "p90_abs_error_mw": m["p90_abs_error_mw"],
                "coverage_pct": m["coverage_pct"],
            }
        )
        cursor += timedelta(days=1)
    return rows


def versions(target: datetime, cutoff: datetime) -> dict:
    """/api/forecast-versions: every version published for one interval, split at the
    cutoff. Exactly one selected (latest available, even with null generation);
    none selected when no version is available. Sorted by publishTime ascending."""
    _ensure_loaded()
    entries = []
    best_pub = None
    best_index = None
    for row in sorted(_FORECASTS_BY_START.get(target, []), key=lambda r: r["publish_time"]):
        pub = timeutil.parse_utc(row["publish_time"])
        available = pub <= cutoff
        entries.append(
            {
                "publish_time": timeutil.iso_z(pub),
                "forecast_mw": row["generation"],
                "lead_time_h": (target - pub).total_seconds() / 3600.0,
                "available_at_cutoff": available,
                "selected": False,
            }
        )
        if available and (best_pub is None or pub > best_pub):
            best_pub = pub
            best_index = len(entries) - 1
    if best_index is not None:
        entries[best_index]["selected"] = True
    return {
        "target_time": timeutil.iso_z(target),
        "cutoff_utc": timeutil.iso_z(cutoff),
        "versions": entries,
    }


def lead_time_buckets(bucket_hours: int) -> list[dict]:
    """/api/metrics/by-lead-time: metrics per lead-time bucket over ALL versions.

    Scope: publishTime in [2026-01-01, 2026-02-01), startTime
    in [2026-01-02, 2026-02-02), startTime > publishTime, generation not null, and
    a non-null actual at the same startTime. Closed buckets are [k*bh, min((k+1)*bh,
    48)); everything >= 48 h falls in the final open-ended bucket (end = None).
    Empty buckets are returned with null metrics; edges are half-open.
    """
    _ensure_loaded()
    top = config.LEAD_BUCKET_TOP_H
    closed: list[tuple[int, int]] = []
    k = 0
    while k * bucket_hours < top:
        closed.append((k * bucket_hours, min((k + 1) * bucket_hours, top)))
        k += 1
    errors_per_bucket: list[list[float]] = [[] for _ in closed]
    open_errors: list[float] = []

    for row in _FORECASTS:
        start = timeutil.parse_utc(row["start_time"])
        if not (_LEAD_START_START <= start < _LEAD_START_END_EXCL):
            continue
        pub = timeutil.parse_utc(row["publish_time"])
        if not (_LEAD_PUB_START <= pub < _LEAD_PUB_END_EXCL):
            continue
        gen = row["generation"]
        if gen is None or start <= pub:
            continue
        actual = _ACTUALS_BY_DT.get(start)
        if actual is None:
            continue
        err = gen - actual
        lead = (start - pub).total_seconds() / 3600.0
        if lead >= top:
            open_errors.append(err)
        else:
            bucket = int(lead // bucket_hours)
            errors_per_bucket[bucket].append(err)

    rows = []
    for (b_start, b_end), errs in zip(closed, errors_per_bucket):
        m = metrics.compute_metrics(errs)
        rows.append({"bucket_start_h": b_start, "bucket_end_h": b_end, "n": m["n"],
                     "bias_mw": m["bias_mw"], "mae_mw": m["mae_mw"], "rmse_mw": m["rmse_mw"]})
    m = metrics.compute_metrics(open_errors)
    rows.append({"bucket_start_h": top, "bucket_end_h": None, "n": m["n"],
                 "bias_mw": m["bias_mw"], "mae_mw": m["mae_mw"], "rmse_mw": m["rmse_mw"]})
    return rows
