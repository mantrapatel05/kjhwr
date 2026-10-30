# -*- coding: utf-8 -*-
"""Forecast error metrics (file 04). PURE: no I/O, no FastAPI.

Convention: error = forecast - actual (MW). e > 0 → over-forecast.
All metrics use matched, non-null pairs only. n == 0 → null metrics, never NaN.

P90 uses linear interpolation — equivalent of numpy.percentile(..., 90) default
("linear"), stated as such in the README. numpy is NOT a dependency (file 08 §1
keeps the image small); the hand-checkable case in file 04 §25 pins the values.
MAPE is deliberately absent: actual wind can be near zero and it explodes (file 04).
"""

from __future__ import annotations

import math

_FIELDS = ("bias_mw", "mae_mw", "rmse_mw", "p90_abs_error_mw", "max_abs_error_mw")


def compute_metrics(errors) -> dict:
    """All core metrics over matched error values. Returns n + MW fields (+None)."""
    clean = [float(e) for e in errors if e is not None]
    n = len(clean)
    if n == 0:
        return {"n": 0, **{k: None for k in _FIELDS}}

    bias = sum(clean) / n
    mae = sum(abs(e) for e in clean) / n
    rmse = math.sqrt(sum(e * e for e in clean) / n)
    abs_sorted = sorted(abs(e) for e in clean)
    p90 = _percentile_linear(abs_sorted, 90)

    return {
        "n": n,
        "bias_mw": bias,
        "mae_mw": mae,
        "rmse_mw": rmse,
        "p90_abs_error_mw": p90,
        "max_abs_error_mw": abs_sorted[-1],
    }


def _percentile_linear(sorted_vals: list[float], pct: float) -> float:
    """numpy 'linear' method: pos = pct/100 * (n-1), interpolate between ranks."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = (pct / 100.0) * (len(sorted_vals) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(sorted_vals[lo])
    frac = pos - lo
    return float(sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo]))
