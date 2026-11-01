# -*- coding: utf-8 -*-
"""Service layer (file 05 §1): the ONE orchestration point.

routes.py stays thin; ALL orchestration lives here. The snapshot is loaded ONCE
per process (at first data access) and kept in memory for its lifetime — the
deployed app never reads the network or data/raw/ at runtime (file 02 §4).

Computed days are cached per (decision_date, cutoff): the 31 x 5 combinations are
tiny, and each is deterministic from the frozen snapshot, so an unbounded cache
is correct and cheap.
"""

from __future__ import annotations

from functools import lru_cache

from . import config, data_store, processing

_FORECASTS: list | None = None
_ACTUALS: dict | None = None


def load() -> None:
    """Load and validate the snapshot once. Fail fast on missing/malformed files."""
    global _FORECASTS, _ACTUALS
    snapshot = data_store.load_snapshot()
    _FORECASTS = snapshot["forecasts"]
    _ACTUALS = data_store.actuals_by_start(snapshot)
    _day_cache.cache_clear()  # a reload invalidates every cached day


def loaded() -> bool:
    return _FORECASTS is not None


def _ensure_loaded() -> None:
    if _FORECASTS is None:
        load()


@lru_cache(maxsize=None)
def _day_cache(decision_date: str, cutoff: str):
    """True cache, keyed only by plain strings (must stay (date, cutoff)-addressable)."""
    return processing.as_of_series(decision_date, cutoff, _FORECASTS, _ACTUALS)


def day(decision_date: str, cutoff: str | None = None) -> dict:
    """/api/forecast-vs-actual payload for one decision (config default cutoff if None)."""
    _ensure_loaded()
    return _day_cache(decision_date, cutoff or config.DEFAULT_CUTOFF)
