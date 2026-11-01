# -*- coding: utf-8 -*-
"""Test bootstrap: import paths, plus a TINY fixture snapshot for the API tests.

The fixture snapshot is generated at import time and pointed at via the
SNAPSHOT_DIR env var override (data_store reads it at load time). It is hand-made
with HYPOTHETICAL numbers shaped like file 03 §5 — deliberately NOT live data.

Fixture layout (decision 2026-01-15, delivery 2026-01-16, cutoff 09:00):
  delivery hour 10:00Z -> versions 5500@04:30, 5200@07:30, 4800@09:30 (after cutoff)
  delivery hour 11:00Z -> version 5500@04:30 then NULL@07:30 (no fallback rule)
  delivery hour 12:00Z -> version 5000@07:30
  a negative-lead version (startTime < publishTime) for lead-time exclusion
  a late version published outside the January decision scope
  FUELHH actuals at 10:00 (4700), 10:30 (4690), 11:00 (null), 12:00 (0 = real),
    13:00 (300, no forecast), and 2026-01-15T10:00 (pairs with the negative-lead it).
"""

from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SCRIPTS_DIR = BACKEND_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# ---------------------------------------------------------------- fixture snapshot

FIXTURE_DIR = Path(tempfile.gettempdir()) / "reint-fixture-snapshot"
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

_D = "2026-01-15"  # decision day
_V = "2026-01-16"  # delivery day

_WINDFOR = [
    {"start_time": f"{_V}T10:00:00Z", "publish_time": "2026-01-15T04:30:00Z", "generation": 5500.0},
    {"start_time": f"{_V}T10:00:00Z", "publish_time": "2026-01-15T07:30:00Z", "generation": 5200.0},
    {"start_time": f"{_V}T10:00:00Z", "publish_time": "2026-01-15T09:30:00Z", "generation": 4800.0},
    {"start_time": f"{_V}T10:00:00Z", "publish_time": "2026-01-15T11:00:00Z", "generation": 7777.0},
    {"start_time": f"{_V}T10:00:00Z", "publish_time": "2026-01-20T01:00:00Z", "generation": 9999.0},
    {"start_time": f"{_V}T11:00:00Z", "publish_time": "2026-01-15T04:30:00Z", "generation": 5500.0},
    {"start_time": f"{_V}T11:00:00Z", "publish_time": "2026-01-15T07:30:00Z", "generation": None},
    {"start_time": f"{_V}T12:00:00Z", "publish_time": "2026-01-15T07:30:00Z", "generation": 5000.0},
]

_FUELHH = [
    {"start_time": f"{_V}T10:00:00Z", "generation": 4700.0},
    {"start_time": f"{_V}T10:30:00Z", "generation": 4690.0},
    {"start_time": f"{_V}T11:00:00Z", "generation": None},
    {"start_time": f"{_V}T12:00:00Z", "generation": 0.0},
    {"start_time": f"{_V}T13:00:00Z", "generation": 300.0},
    {"start_time": "2026-01-15T10:00:00Z", "generation": 100.0},
]

_META = {
    "fetched_at_utc": "2026-10-30T17:34:55Z",
    "note": "tiny fixture snapshot written by conftest (hypothetical numbers)",
}


def _write_jsonl_gz(path: Path, records: list[dict]) -> None:
    lines = "\n".join(json.dumps(r, separators=(",", ":")) for r in records)
    with gzip.open(path, "wb") as fh:
        fh.write(lines.encode("utf-8"))


def _build_fixture() -> None:
    _write_jsonl_gz(FIXTURE_DIR / "windfor.json.gz", _WINDFOR)
    _write_jsonl_gz(FIXTURE_DIR / "fuelhh_wind.json.gz", _FUELHH)
    (FIXTURE_DIR / "snapshot_meta.json").write_text(json.dumps(_META, indent=2), encoding="utf-8")


_build_fixture()
os.environ["SNAPSHOT_DIR"] = str(FIXTURE_DIR)  # read at load time, not import of data_store
