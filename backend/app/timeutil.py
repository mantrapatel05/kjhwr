# -*- coding: utf-8 -*-
"""Time parsing and window helpers (file 03 §2). PURE: no I/O, no FastAPI.

Every timestamp in the app is UTC and timezone-aware; January is GMT, so UTC
equals UK local time and NO conversion is ever applied (file 03 §7).
Naive datetimes are rejected, not silently assumed (hard rule 3).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

UTC = timezone.utc


# ------------------------------------------------------------------ parsing

def parse_utc(value: str | datetime) -> datetime:
    """'2026-01-15T10:00:00Z' (or +00:00, or an aware datetime) -> aware datetime in UTC.

    Raises ValueError on naive input — a timestamp without an explicit offset can
    only come from a bug, and assuming UTC would hide it (file 03 §7, hard rule 3).
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError(f"naive datetime rejected (no timezone offset): {value!r}")
        return value.astimezone(UTC)
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"naive datetime string rejected (no offset): {value!r}")
    return dt.astimezone(UTC)


import logging
import re

_DECISION_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_decision_date(value: str | date) -> date:
    """'2026-01-15' -> datetime.date. Rejects ANY other shape (e.g. '2026-1-15')
    and impossible calendar dates; no silent recovery (file 03 §7, hard rule 3)."""
    if isinstance(value, date):
        return value
    text = str(value)
    if not _DECISION_SHAPE.match(text):
        raise ValueError(f"invalid decision date (expected YYYY-MM-DD): {value!r}")
    return datetime.strptime(text, "%Y-%m-%d").date()


def parse_time_of_day(hhmm: str) -> tuple[int, int]:
    """'09:00' -> (9, 0). Raises on anything not strictly HH:MM (00-23, 00-59)."""
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
    """Decision day d targets delivery day D = d + 1.

    Returns [D 00:00Z, (D+1) 00:00Z) — half-open, per file 03 §2. Decision day
    2026-01-31 therefore maps to delivery day 2026-02-01.
    """
    d = parse_decision_date(decision_date)
    start = datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(days=1)
    return start, start + timedelta(days=1)


def decision_cutoff(decision_date: str | date, hhmm: str) -> datetime:
    """Decision day d at HH:MM UTC (file 03 §2). Explicit parameter, never hardcoded."""
    d = parse_decision_date(decision_date)
    h, m = parse_time_of_day(hhmm)
    return datetime(d.year, d.month, d.day, h, m, tzinfo=UTC)
