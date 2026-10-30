# -*- coding: utf-8 -*-
"""In-memory snapshot store (file 05). The ONLY impure module besides scripts.

Loads the frozen January-2026 snapshot once; the deployed function keeps it in
memory for its lifetime. No Elexon calls at request time — ever (file 02 §4).
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

SNAP_DIR = Path(__file__).resolve().parents[1] / "data" / "snapshot"


def _read_jsonl_gz(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_snapshot(data_dir: Path = SNAP_DIR) -> dict:
    """Return {'forecasts': [...], 'actuals': [...], 'meta': {...}} from the snapshot.

    Normalised shapes (file 05 §3):
      forecasts: {"start_time", "publish_time", "generation"}   (all WINDFOR versions,
                 nulls kept as None — missing stays missing, never filled)
      actuals:   {"start_time", "generation"}                   (WIND only, by contract
                 enforced in the fetch script; fuelType was verified 100% WIND)
    """
    forecasts = _read_jsonl_gz(data_dir / "windfor.json.gz")
    actuals_raw = _read_jsonl_gz(data_dir / "fuelhh.json.gz")

    actuals = [
        {"start_time": r["start_time"], "generation": r["generation"]}
        for r in actuals_raw
    ]
    meta_path = data_dir / "snapshot_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    # Nowhere else to honestly say this: the snapshot is the data this app presents.
    return {"forecasts": forecasts, "actuals": actuals, "meta": meta}


def actuals_by_start(snapshot: dict) -> dict:
    """{start_time str: generation float|None} — the shape `processing.match` consumes."""
    return {r["start_time"]: r["generation"] for r in snapshot["actuals"]}
