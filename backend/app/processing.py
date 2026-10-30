# -*- coding: utf-8 -*-
"""Core as-of forecast selection and matching (file 03).

PURE module: no file/network I/O, no FastAPI imports. Tests (file 07) pin every rule.
The leakage rule lives here and is non-negotiable: a forecast published after the
decision cutoff may never influence anything downstream.

Vocabulary (file 03 §1):
- delivery interval: the time a forecast is ABOUT (startTime)
- publish time: when a forecast VERSION became known (publishTime)
- decision cutoff: the timestamp the purchase decision is made
- eligible forecast: publishTime <= cutoff (inclusive)
- as-of forecast: per delivery interval, the eligible version with the greatest publishTime
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger(__name__)

UTC = timezone.utc


# ------------------------------------------------------------------ parsing

def parse_utc(value: str | datetime) -> datetime:
    """'2026-01-15T10:00:00Z' (or +00:00) -> aware datetime in UTC. Never naive."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_decision_date(value: str | date) -> date:
    """'2026-01-15' -> datetime.date. Raises on any other shape; no silent recovery."""
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def parse_time_of_day(hhmm: str) -> tuple[int, int]:
    """'09:00' -> (9, 0). Raises on anything not HH:MM (00-23, 00-59)."""
    parts = str(hhmm).split(":")
    ok = (
        len(parts) == 2
        and all(p.isdigit() and len(p) == 2 for p in parts)
        and 0 <= int(parts[0]) <= 23
        and 0 <= int(parts[1]) <= 59
    )
    if not ok:
        raise ValueError(f"invalid HH:MM: {hhmm!r}")
    return int(parts[0]), int(parts[1])


# ------------------------------------------------------------------ windows

def delivery_window(decision_date: str | date) -> tuple[datetime, datetime]:
    """Decision day d targets delivery day D = d+1.

    Returns [D 00:00Z, (D+1) 00:00Z) — half-open, per file 03 §2.
    """
    d = parse_decision_date(decision_date)
    start = datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(days=1)
    return start, start + timedelta(days=1)


def decision_cutoff(decision_date: str | date, hhmm: str) -> datetime:
    """Decision day d at HH:MM UTC (file 03 §2). Explicit parameter, never hardcoded."""
    d = parse_decision_date(decision_date)
    h, m = parse_time_of_day(hhmm)
    return datetime(d.year, d.month, d.day, h, m, tzinfo=UTC)


# ------------------------------------------------------------------ selection

def select_as_of(
    forecasts, cutoff: datetime, win_start: datetime, win_end: datetime
) -> dict[datetime, dict]:
    """As-of selection (file 03 §3 steps 3-4, §7 dedupe rule).

    forecasts: iterable of dicts with start_time / publish_time / generation.
    Returns {start_time(datetime): chosen record} where the record has parsed
    datetimes and generation as given (None stays None).

    Rules implemented:
      - keep startTime in [win_start, win_end) AND publishTime <= cutoff (inclusive)
      - latest publishTime per startTime wins (strictly greater replaces)
      - duplicate (startTime, publishTime): first occurrence kept; a later one with a
        DIFFERENT generation replaces it with a warning (last-of-file wins, file 03 §7)
    """
    cutoff = parse_utc(cutoff)
    win_start = parse_utc(win_start)
    win_end = parse_utc(win_end)

    seen_keys: dict[tuple[datetime, datetime], dict] = {}
    for row in forecasts:
        st = parse_utc(row["start_time"])
        pt = parse_utc(row["publish_time"])
        gen = row.get("generation")
        if not (win_start <= st < win_end):
            continue
        if pt > cutoff:  # leakage guard — inclusive cutoff
            continue
        key = (st, pt)
        prior = seen_keys.get(key)
        if prior is not None and prior["generation"] != gen:
            logger.warning(
                "conflicting duplicate WINDFOR row (startTime=%s publishTime=%s): "
                "keeping the later generation=%s over %s",
                st.isoformat(), pt.isoformat(), gen, prior["generation"],
            )
        seen_keys[key] = {"start_time": st, "publish_time": pt, "generation": gen}

    chosen: dict[datetime, dict] = {}
    for (st, pt), rec in seen_keys.items():
        cur = chosen.get(st)
        if cur is None or pt > cur["publish_time"]:
            chosen[st] = rec
    return chosen


# ------------------------------------------------------------------ matching

def match(chosen: dict, actuals: dict) -> tuple[list[dict], list[dict]]:
    """Join as-of forecasts with actuals on identical startTime (file 03 §3 steps 6-7).

    chosen:  {start_time(datetime): {"start_time", "publish_time", "generation"}}
    actuals: {start_time(datetime): generation(float | None)}

    Returns (points, actuals_only):
      - points: one row per chosen interval (matched or not); never 0 for missing;
        error = generation - actual ONLY when both sides are non-null (file 03 §7 step 7)
      - actuals_only: window actuals (e.g. :30 half-hours, hourly forecast product)
        with NO chosen forecast — shown separately, never interpolated (file 03 §6)
    Point shape follows file 05 (forecast_mw / actual_mw / lead_time_h / error_mw).
    """
    points: list[dict] = []
    for st in sorted(chosen):
        rec = chosen[st]
        f, a = rec["generation"], actuals.get(st)
        matched = f is not None and a is not None
        lead_h = (st - rec["publish_time"]).total_seconds() / 3600.0
        points.append(
            {
                "start_time": st.isoformat().replace("+00:00", "Z"),
                "forecast_mw": f,
                "actual_mw": a,
                "publish_time": rec["publish_time"].isoformat().replace("+00:00", "Z"),
                "lead_time_h": lead_h,
                "error_mw": (f - a) if matched else None,
                "matched": matched,
            }
        )

    actuals_only = []
    for st in sorted(set(actuals) - set(chosen)):
        a = actuals[st]
        if a is not None:
            actuals_only.append(
                {"start_time": st.isoformat().replace("+00:00", "Z"), "actual_mw": a}
            )
    return points, actuals_only


# ------------------------------------------------------------------ series

def as_of_series(decision_date: str | date, cutoff_hhmm: str, forecasts, actuals) -> dict:
    """Everything the /api/forecast-vs-actual endpoint needs, for one decision (file 05).

    actuals: {start_time(datetime or str): generation(float | None)}

    expected_points = distinct forecast startTimes in the window across ALL WINDFOR
    versions (the product's hourly grid; 24 in January). Coverage uses this, per
    file 03 §3 step 8. A delivery day with no matched points yields n=0 metrics
    and coverage 0.0 — never NaN, never an error.
    """
    cutoff = decision_cutoff(decision_date, cutoff_hhmm)
    win_start, win_end = delivery_window(decision_date)

    candidates = {
        parse_utc(rec["start_time"])
        for rec in forecasts
        if win_start <= parse_utc(rec["start_time"]) < win_end
    }
    expected = len(candidates) if candidates else 24  # hourly grid fallback (Jan = GMT)

    chosen = select_as_of(forecasts, cutoff, win_start, win_end)

    actuals_dt = {parse_utc(k): v for k, v in actuals.items()}
    actuals_in_window = {
        st: a for st, a in actuals_dt.items() if win_start <= st < win_end
    }

    points, actuals_only = match(chosen, actuals_in_window)
    metrics = compute_metrics([p["error_mw"] for p in points])
    matched = sum(1 for p in points if p["matched"])
    d = parse_decision_date(decision_date)

    return {
        "decision_date": d.isoformat(),
        "cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "delivery_day": (d + timedelta(days=1)).isoformat(),
        "expected_points": expected,
        "matched_points": matched,
        "points": points,
        "actuals_only": actuals_only,
        "metrics": {**metrics, "coverage_pct": (matched / expected) * 100.0 if expected else 0.0},
    }


# metrics import at bottom avoids a circular import while keeping this module
# single-responsibility; compute_metrics is pure and stateless.
from .metrics import compute_metrics  # noqa: E402
