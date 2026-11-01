# -*- coding: utf-8 -*-
"""Timeutil tests (file 07 §TESTS): parsing, cutoff builder, delivery-window bounds."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.timeutil import (
    decision_cutoff,
    delivery_window,
    parse_decision_date,
    parse_time_of_day,
    parse_utc,
)


# ---------------------------------------------------------------- parse_utc

def test_parse_utc_handles_z_suffix():
    dt = parse_utc("2026-01-15T10:00:00Z")
    assert dt == datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    assert dt.tzinfo is timezone.utc


def test_parse_utc_handles_offset_form():
    assert parse_utc("2026-01-15T10:00:00+00:00") == datetime(
        2026, 1, 15, 10, 0, tzinfo=timezone.utc
    )


def test_parse_utc_rejects_naive_string():
    with pytest.raises(ValueError):
        parse_utc("2026-01-15T10:00:00")           # no offset → reject, never assume


def test_parse_utc_rejects_date_only_string():
    with pytest.raises(ValueError):
        parse_utc("2026-01-15")                    # use parse_decision_date for dates


def test_parse_utc_accepts_aware_datetime():
    aware = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    assert parse_utc(aware) == aware


# ---------------------------------------------------------------- decision dates + HH:MM

def test_parse_decision_date_valid():
    assert parse_decision_date("2026-01-15") == date(2026, 1, 15)


def test_parse_decision_date_passes_through_date_object():
    assert parse_decision_date(date(2026, 1, 15)) == date(2026, 1, 15)


@pytest.mark.parametrize("bad", ["2026-1-15", "15-01-2026", "not-a-date", ""])
def test_parse_decision_date_rejects_other_shapes(bad):
    with pytest.raises(ValueError):
        parse_decision_date(bad)


def test_parse_time_of_day_valid():
    assert parse_time_of_day("09:00") == (9, 0)
    assert parse_time_of_day("23:59") == (23, 59)


@pytest.mark.parametrize("bad", ["9:00", "24:00", "ab:cd", "0900", "", "09:60"])
def test_parse_time_of_day_rejects_non_hhmm(bad):
    with pytest.raises(ValueError):
        parse_time_of_day(bad)


# ---------------------------------------------------------------- cutoff + windows

def test_decision_cutoff_builds_aware_utc():
    cutoff = decision_cutoff("2026-01-15", "09:00")
    assert cutoff == datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)


def test_delivery_window_is_half_open_next_day():
    start, end = delivery_window("2026-01-15")
    assert start == datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 1, 17, 0, 0, tzinfo=timezone.utc)


def test_delivery_window_jan31_maps_to_feb1():
    """Decision on Jan 31 → delivery Feb 1 (spec-mandated boundary case)."""
    start, end = delivery_window("2026-01-31")
    assert start == datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 2, 2, 0, 0, tzinfo=timezone.utc)
