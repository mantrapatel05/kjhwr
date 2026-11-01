"""Snapshot validation tests for the production data reader."""

from __future__ import annotations

import gzip
import json

import pytest

from app import data_store


def _write_snapshot(tmp_path, forecasts, actuals):
    for name, rows in (
        (data_store.WINDFOR_FILE, forecasts),
        (data_store.FUELHH_FILE, actuals),
    ):
        with gzip.open(tmp_path / name, "wt", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row) + "\n")


def test_load_snapshot_accepts_aware_times_and_nullable_generation(tmp_path):
    _write_snapshot(
        tmp_path,
        [{"start_time": "2026-01-02T00:00:00Z", "publish_time": "2026-01-01T00:00:00Z", "generation": None}],
        [{"start_time": "2026-01-02T00:00:00Z", "generation": 0}],
    )

    snapshot = data_store.load_snapshot(tmp_path)

    assert snapshot["forecasts"][0]["generation"] is None
    assert snapshot["actuals"][0]["generation"] == 0


@pytest.mark.parametrize(
    ("forecasts", "actuals", "file_name", "message"),
    [
        ([{"start_time": "not-a-time", "publish_time": "2026-01-01T00:00:00Z", "generation": 1}], [], data_store.WINDFOR_FILE, "start_time"),
        ([{"start_time": "2026-01-02T00:00:00Z", "publish_time": "2026-01-01T00:00:00Z", "generation": "7"}], [], data_store.WINDFOR_FILE, "generation"),
        ([], [{"start_time": "2026-01-02T00:00:00Z", "generation": "0"}], data_store.FUELHH_FILE, "generation"),
        ([], [{"start_time": "2026-01-02T00:00:00" , "generation": 0}], data_store.FUELHH_FILE, "start_time"),
    ],
)
def test_load_snapshot_rejects_invalid_rows(tmp_path, forecasts, actuals, file_name, message):
    _write_snapshot(tmp_path, forecasts, actuals)

    with pytest.raises(ValueError, match=rf"{file_name}.*{message}"):
        data_store.load_snapshot(tmp_path)
