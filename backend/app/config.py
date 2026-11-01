# -*- coding: utf-8 -*-
"""Constants: single source of truth (file 01 §6).

All times are UTC — January is GMT, so UTC equals UK local time; never convert.
Delivery day for decision date d is d + 1 (enforced in timeutil.delivery_window),
so decision dates map to delivery days 2026-01-02 .. 2026-02-01.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

# ------------------------------------------------------------------ decision window

DECISION_FROM = "2026-01-01"
DECISION_TO = "2026-01-31"  # inclusive decision dates

# Derived (decision + 1 day); declared here so /api/config needs no computation.
DELIVERY_FROM = "2026-01-02"
DELIVERY_TO = "2026-02-01"

# Cutoff is an explicit, visible parameter everywhere — never silently hardcoded.
DEFAULT_CUTOFF = "09:00"  # UTC, on the decision date (the day before delivery)

# UI convenience only; the API accepts any valid HH:MM.
CUTOFF_OPTIONS = ["06:00", "08:00", "09:00", "10:00", "12:00"]

TIMEZONE_NOTE = "All times UTC; UK is on GMT (UTC+0) in January."

# ------------------------------------------------------------------ lead-time analysis

LEAD_BUCKET_HOURS_DEFAULT = 6
LEAD_BUCKET_HOURS_MIN = 1  # endpoint validation: integer 1..24
LEAD_BUCKET_HOURS_MAX = 24
LEAD_BUCKET_TOP_H = 48  # buckets run 0..48 h; everything >= 48 h is the final
#                        open-ended bucket (bucket_end_h = None).

# ------------------------------------------------------------------ snapshot location

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SNAPSHOT_DIR = DATA_DIR / "snapshot"  # overridden by env var SNAPSHOT_DIR (tests use it)

# ------------------------------------------------------------------ fetch windows

# Used ONLY by scripts/fetch_elexon.py. Over-fetching here is deliberate:
# processing enforces the exact decision/delivery limits (file 01 §6).
FETCH_WINDFOR_PUBLISH_FROM = datetime(2025, 12, 28, 0, 0, tzinfo=timezone.utc)
FETCH_WINDFOR_PUBLISH_TO = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
FETCH_FUELHH_SETTLEMENT_FROM = date(2026, 1, 1)
FETCH_FUELHH_SETTLEMENT_TO = date(2026, 2, 2)

CHUNK_DAYS = 7  # contiguous, non-overlapping chunks
