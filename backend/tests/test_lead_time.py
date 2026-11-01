# -*- coding: utf-8 -*-
"""Lead-time analysis tests (file 07 §TESTS): bucket edges, scope, exclusions.

Uses the fixture snapshot loaded into service (SNAPSHOT_DIR override, conftest).

Bucket expectations for the fixture (bucket_hours=6):
  in-scope matched versions: 5500@04:30 (lead 29.5, err +800),
  5200@07:30 (26.5, +500), 4800@09:30 (24.5, +100) for hour 10,
  and 5000@07:30 (28.5, +5000) for hour 12  -> all in [24, 30): n = 4
  EXCLUDED: null-generation version (hour 11, null actual too); the version whose
  startTime < publishTime; the out-of-scope January-window publish.
"""

from __future__ import annotations

from app import service


def test_bucket_windows_and_exclusions():
    rows = service.lead_time_buckets(6)
    assert len(rows) == 9                                   # 8 closed (0..48) + open
    assert [r["bucket_end_h"] for r in rows[:-1]] == [6, 12, 18, 24, 30, 36, 42, 48]
    bucket_24_30 = rows[4]                                  # [24, 30)
    assert bucket_24_30["bucket_start_h"] == 24 and bucket_24_30["bucket_end_h"] == 30
    assert bucket_24_30["n"] == 4                           # see module docstring
    assert bucket_24_30["bias_mw"] == (800 + 500 + 100 + 5000) / 4    # 1600.0
    assert bucket_24_30["mae_mw"] == 1600.0
    assert abs(bucket_24_30["rmse_mw"] - ((
        (800 ** 2 + 500 ** 2 + 100 ** 2 + 5000 ** 2) / 4
    ) ** 0.5)) < 1e-3


def test_empty_buckets_have_null_metrics():
    rows = service.lead_time_buckets(6)
    low = rows[0]                                           # [0, 6): no such leads
    assert low["n"] == 0
    assert low["bias_mw"] is None and low["mae_mw"] is None and low["rmse_mw"] is None
    assert rows[-1]["n"] == 0 and rows[-1]["bucket_end_h"] is None


def test_bucket_hours_changes_edges():
    rows = service.lead_time_buckets(24)
    assert len(rows) == 3                                   # [0,24) [24,48) open
    assert rows[-1]["bucket_start_h"] == 48 and rows[-1]["bucket_end_h"] is None
    assert rows[1]["n"] == 4                                # all fixture leads 24..30
