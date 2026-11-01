# -*- coding: utf-8 -*-
"""Matching tests M1-M4 plus the null-forecast match rule (file 07 §2).

Fixtures are hand-made with HYPOTHETICAL numbers from file 03 §5 — not live data.
"""

from __future__ import annotations

from app import processing as P
from app.timeutil import parse_utc

# file 03 §5 reference interval: delivery 2026-01-16T10:00Z, decision 2026-01-15
T10 = "2026-01-16T10:00:00Z"
WIN = ("2026-01-16T00:00:00Z", "2026-01-17T00:00:00Z")
V730 = ("2026-01-15T07:30:00Z", 5200)


def fc(st: str, pt: str, gen):
    return {"start_time": st, "publish_time": pt, "generation": gen}


def _match_two(actual_map):
    chosen = P.select_as_of([fc(T10, V730[0], V730[1])], "2026-01-15T09:00:00Z", *WIN)
    return P.match(chosen, actual_map)


def test_m1_same_starttime_matched():
    points, _ = _match_two({parse_utc(T10): 4700.0})
    (pt,) = points
    assert pt["matched"] and pt["error_mw"] == 5200 - 4700      # +500 over-forecast
    assert pt["publish_time"].startswith("2026-01-15T07:30")


def test_m2_halfhour_actual_only():
    act = {parse_utc(T10): 4700.0, parse_utc("2026-01-16T10:30:00Z"): 4690.0}
    points, only = _match_two(act)
    assert all(pt["start_time"] != "2026-01-16T10:30:00Z" for pt in points)
    assert only == [{"start_time": "2026-01-16T10:30:00Z", "actual_mw": 4690.0}]


def test_m3_actual_missing():
    points, _ = _match_two({parse_utc(T10): None})
    (pt,) = points
    assert pt["matched"] is False and pt["error_mw"] is None   # unmatched ≠ 0


def test_m4_zero_actual_valid():
    points, _ = _match_two({parse_utc(T10): 0.0})
    (pt,) = points
    assert pt["matched"] is True                               # zero wind is real
    assert pt["error_mw"] == 5200


def test_match_null_forecast_not_matched():
    """null latest version + actual present → point exists, matched False, actual NOT zeroed."""
    chosen = P.select_as_of([fc(T10, V730[0], None)], "2026-01-15T09:00:00Z", *WIN)
    points, _ = P.match(chosen, {parse_utc(T10): 4700.0})
    (point,) = points
    assert point["forecast_mw"] is None and point["matched"] is False
    assert point["error_mw"] is None and point["actual_mw"] == 4700
