# -*- coding: utf-8 -*-
"""Metric tests from file 04's hand-checkable case (file 07 §3)."""

from __future__ import annotations

import math

from app.metrics import _percentile_linear, compute_metrics

HAND = [800.0, -200.0, 0.0, -600.0]     # F=[5000,4800,3000,2400], A=[4200,5000,3000,3000]


def test_hand_case_file04():
    m = compute_metrics(HAND)
    assert m["n"] == 4
    assert m["bias_mw"] == 0.0                                # (800-200+0-600)/4
    assert m["mae_mw"] == 400.0                               # (800+200+0+600)/4
    assert math.isclose(m["rmse_mw"], math.sqrt(260000), rel_tol=1e-12)   # ≈ 509.902
    assert m["p90_abs_error_mw"] == 740.0                     # linear 90th pctile
    assert m["max_abs_error_mw"] == 800.0


def test_single_pair():
    m = compute_metrics([800.0])
    assert (m["n"], m["bias_mw"], m["mae_mw"], m["rmse_mw"],
            m["p90_abs_error_mw"], m["max_abs_error_mw"]) == (1, 800.0, 800.0, 800.0, 800.0, 800.0)


def test_empty_input_no_exception():
    m = compute_metrics([])
    assert m["n"] == 0 and all(m[k] is None for k in
                               ("bias_mw", "mae_mw", "rmse_mw", "p90_abs_error_mw", "max_abs_error_mw"))


def test_none_entries_ignored():
    m = compute_metrics([800.0, None, -200.0])
    assert m["n"] == 2 and m["mae_mw"] == 500.0


def test_rmse_ge_mae():
    m = compute_metrics(HAND)
    assert m["rmse_mw"] >= m["mae_mw"]


def test_sign_convention_forecast_higher_positive():
    assert compute_metrics([500.0])["bias_mw"] > 0            # F > A → over-forecast
    assert compute_metrics([-500.0])["bias_mw"] < 0           # F < A → under-forecast


def test_percentile_linear_exact_ranks():
    vals = [0.0, 200.0, 600.0, 800.0]
    assert _percentile_linear(vals, 90) == 740.0              # 600 + 0.7*(800-600)
    assert _percentile_linear(vals, 100) == 800.0
    assert _percentile_linear(vals, 0) == 0.0
    assert _percentile_linear(vals, 50) == 400.0              # between 200 and 600
