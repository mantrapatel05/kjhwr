from __future__ import annotations

import copy

import recompute_day as R


def _matching_payloads():
    mine = {
        "decision_date": "2026-01-05",
        "cutoff_utc": "2026-01-05T09:00:00Z",
        "delivery_day": "2026-01-06",
        "expected_points": 24,
        "matched_points": 24,
        "coverage_pct": 100.0,
        "metrics": {
            "n": 24,
            "bias_mw": 10.1234,
            "mae_mw": 20.1234,
            "rmse_mw": 30.1234,
            "p90_abs_error_mw": 40.1234,
            "max_abs_error_mw": 50.1234,
        },
    }
    theirs = {
        "decision_date": "2026-01-05",
        "cutoff_utc": "2026-01-05T09:00:00Z",
        "delivery_day": "2026-01-06",
        "expected_points": 24,
        "matched_points": 24,
        "metrics": {
            "n": 24,
            "expected": 24,
            "coverage_pct": 100.0,
            "bias_mw": 10.123,
            "mae_mw": 20.123,
            "rmse_mw": 30.123,
            "p90_abs_error_mw": 40.123,
            "max_abs_error_mw": 50.123,
        },
    }
    return mine, theirs


def test_comparison_checks_all_rounded_metrics():
    mine, theirs = _matching_payloads()
    assert R.comparison_differences(mine, theirs) == []

    changed = copy.deepcopy(theirs)
    changed["metrics"]["p90_abs_error_mw"] = 41.0
    assert R.comparison_differences(mine, changed) == [
        "metrics.p90_abs_error_mw: recompute=40.1234, server=41.0"
    ]


def test_comparison_checks_nulls_and_coverage():
    mine, theirs = _matching_payloads()
    mine["metrics"]["bias_mw"] = None
    theirs["metrics"]["bias_mw"] = None
    theirs["metrics"]["coverage_pct"] = 99.0
    differences = R.comparison_differences(mine, theirs)
    assert differences == ["metrics.coverage_pct: recompute=100.0, server=99.0"]


def test_recompute_expected_counts_all_versions_and_no_synthetic_grid():
    future = {
        "start_time": "2026-01-06T10:00:00Z",
        "publish_time": "2026-01-05T10:00:00Z",
        "generation": 5000,
    }
    empty = R.recompute("2026-01-05", "09:00", [], [])
    future_only = R.recompute("2026-01-05", "09:00", [future], [])

    assert empty["expected_points"] == 0
    assert future_only["expected_points"] == 1
    assert future_only["matched_points"] == 0
