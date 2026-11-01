# -*- coding: utf-8 -*-
"""Fetch/cleaning tests (file 07 §TESTS): pure helpers only — NO network in tests.

Imports the fetch script as a module (conftest puts backend/scripts on sys.path);
the script's own sys.path bootstrap makes `app.config` importable for the windows.
"""

from __future__ import annotations

import gzip
import json
from datetime import date, datetime, timedelta, timezone

import fetch_elexon as F


# ---------------------------------------------------------------- chunking

def test_chunked_datetimes_contiguous_non_overlapping_full_coverage():
    """Chunk n+1 starts exactly when chunk n ends; union covers [start, end)."""
    start = datetime(2025, 12, 28, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    chunks = list(F.chunked_datetimes(start, end, F.CHUNK_DAYS))

    assert chunks[0][0] == start
    for (a_start, a_end), (b_start, b_end) in zip(chunks, chunks[1:]):
        assert a_end == b_start                      # contiguous, not overlapping
    assert chunks[-1][1] == end                      # nothing past the window


def test_chunked_dates_contiguous_inclusive_end():
    """Date chunks walk day-by-day with no gap and keep the inclusive FUELHH end."""
    start, end = date(2026, 1, 1), date(2026, 2, 2)
    chunks = list(F.chunked_dates(start, end, F.CHUNK_DAYS))

    assert chunks[0][0] == start
    for (a_start, a_end), (b_start, b_end) in zip(chunks, chunks[1:]):
        assert b_start == a_end + timedelta(days=1)  # no gap, no overlap
        assert a_start <= a_end                      # never inverted
    assert chunks[-1][1] == end


# ---------------------------------------------------------------- WINDFOR cleaning

def wf(st, pt, gen):
    return {"startTime": st, "publishTime": pt, "generation": gen}


def test_normalise_windfor_dedupes_identical_keys():
    rows = [
        wf("2026-01-16T10:00:00Z", "2026-01-15T07:30:00Z", 5200),
        wf("2026-01-16T10:00:00Z", "2026-01-15T07:30:00Z", 5200),  # exact duplicate
    ]
    out, meta = F.normalise_windfor(rows)
    assert len(out) == 1 and meta["rows_snapshot"] == 1


def test_normalise_windfor_keep_latest_publish_time():
    rows = [
        wf("2026-01-16T10:00:00Z", "2026-01-15T04:30:00Z", 5500),
        wf("2026-01-16T10:00:00Z", "2026-01-15T07:30:00Z", 5200),
    ]
    out, _ = F.normalise_windfor(rows)
    assert len(out) == 2                                   # both versions kept
    assert out[-1]["publish_time"] == "2026-01-15T07:30:00Z"


def test_normalise_windfor_conflicting_duplicate_last_wins():
    rows = [
        wf("2026-01-16T10:00:00Z", "2026-01-15T07:30:00Z", 5100),
        wf("2026-01-16T10:00:00Z", "2026-01-15T07:30:00Z", 5200),
    ]
    out, meta = F.normalise_windfor(rows)
    assert out[0]["generation"] == 5200                    # later row wins
    assert meta["conflicting_duplicates"] == 1


def test_normalise_windfor_drops_rows_missing_required_times():
    rows = [
        wf("2026-01-16T10:00:00Z", None, 5000),            # no publishTime
        wf(None, "2026-01-15T07:30:00Z", 5000),            # no startTime
    ]
    out, meta = F.normalise_windfor(rows)
    assert out == [] and meta["rows_snapshot"] == 0
    assert meta["rows_missing_required_keys"] == 2


def test_normalise_windfor_counts_missing_generation_key():
    row = {"startTime": "2026-01-16T10:00:00Z", "publishTime": "2026-01-15T07:30:00Z"}
    out, meta = F.normalise_windfor([row])
    assert out == []
    assert meta["rows_missing_required_keys"] == 1


def test_normalise_windfor_keeps_null_generation():
    """Missing is missing: a null generation survives cleaning as null."""
    out, _ = F.normalise_windfor([wf("2026-01-16T10:00:00Z", "2026-01-15T07:30:00Z", None)])
    assert out[0]["generation"] is None


# ---------------------------------------------------------------- FUELHH cleaning

def fh(st, gen, fuel, pt=None):
    return {"startTime": st, "generation": gen, "fuelType": fuel, "publishTime": pt}


def test_normalise_fuelhh_wind_only_gate():
    """M5 substance at the fetch layer: non-WIND rows never reach the snapshot."""
    rows = [
        fh("2026-01-16T10:00:00Z", 4700.0, "WIND"),
        fh("2026-01-16T10:00:00Z", 9900.0, "CCGT"),        # must be discarded
        fh("2026-01-16T10:30:00Z", 100.0, "OTHER"),        # also non-WIND: 2 discards
    ]
    out, meta = F.normalise_fuelhh(rows)
    assert [r["start_time"] for r in out] == ["2026-01-16T10:00:00Z"]
    assert meta["non_wind_discarded"] == 2


def test_normalise_fuelhh_duplicate_starttime_latest_publish_wins():
    rows = [
        fh("2026-01-16T10:00:00Z", 4690.0, "WIND", pt="2026-01-16T09:00:00Z"),
        fh("2026-01-16T10:00:00Z", 4700.0, "WIND", pt="2026-01-16T10:00:00Z"),
    ]
    out, meta = F.normalise_fuelhh(rows)
    assert len(out) == 1 and out[0]["generation"] == 4700   # latest publishTime


def test_normalise_fuelhh_zero_generation_is_valid():
    """A real actual of 0 MW is a valid value — never dropped."""
    out, _ = F.normalise_fuelhh([fh("2026-01-16T10:00:00Z", 0, "WIND")])
    assert out[0]["generation"] == 0


def test_normalise_fuelhh_drops_missing_starttime():
    out, meta = F.normalise_fuelhh([fh(None, 4700.0, "WIND")])
    assert out == [] and meta["rows_snapshot"] == 0
    assert meta["rows_missing_required_keys"] == 1


def test_normalise_fuelhh_counts_missing_generation_key():
    row = {"startTime": "2026-01-16T10:00:00Z", "fuelType": "WIND"}
    out, meta = F.normalise_fuelhh([row])
    assert out == []
    assert meta["rows_missing_required_keys"] == 1


# ---------------------------------------------------------------- serialisation

def test_write_jsonl_gz_roundtrip(tmp_path):
    records = [
        {"start_time": "2026-01-16T10:00:00Z", "generation": 4700.0},
        {"start_time": "2026-01-16T10:30:00Z", "generation": None},   # null survives
    ]
    path = tmp_path / "t.json.gz"
    F.write_jsonl_gz(path, records)

    with gzip.open(path, "rt", encoding="utf-8") as fh:
        assert [json.loads(line) for line in fh if line.strip()] == records
