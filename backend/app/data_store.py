# -*- coding: utf-8 -*-
"""In-memory snapshot store (file 05). The ONLY module that reads the snapshot.

The deployed app never calls Elexon at request time — it serves the frozen
January-2026 snapshot committed in data/snapshot/ (file 02 §4). Loads fail fast
with a clear message if snapshot files are missing or malformed. The env var
SNAPSHOT_DIR overrides the default directory (the API contract tests use it to
point at a tiny fixture snapshot).
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

from . import config

WINDFOR_FILE = "windfor.json.gz"
FUELHH_FILE = "fuelhh_wind.json.gz"  # spec file name; WIND-only by construction


def _snapshot_dir(override: Path | str | None) -> Path:
    """Explicit argument wins, then the SNAPSHOT_DIR env var, then the default."""
    if override is not None:
        return Path(override)
    return Path(os.environ.get("SNAPSHOT_DIR", str(config.SNAPSHOT_DIR)))


def _read_jsonl_gz(path: Path) -> list[dict]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
    except (gzip.BadGzipFile, json.JSONDecodeError, UnicodeDecodeError) as exc:
        # Fail fast with a clear message, per file: load and validate ONCE at startup.
        raise ValueError(f"malformed snapshot file {path.name}: {exc}") from exc


def _require_keys(records: list[dict], keys: tuple[str, ...], path: Path) -> None:
    for rec in records:
        for key in keys:
            if key not in rec:
                raise ValueError(
                    f"malformed snapshot file {path.name}: record missing {key!r} ({rec!r})"
                )


def load_snapshot(data_dir: Path | str | None = None) -> dict:
    """Return {'forecasts', 'actuals', 'meta'} from the snapshot. Misspelled or
    truncated files raise immediately — never load half a snapshot.

    Normalised shapes (file 05 §3):
      forecasts: {"start_time", "publish_time", "generation"}   (all WINDFOR versions,
                 nulls kept as None — missing stays missing, never filled)
      actuals:   {"start_time", "generation"}                   (WIND only, enforced in
                 the fetch script's normalise_fuelhh; fuelType verified 100% WIND)
    """
    directory = _snapshot_dir(data_dir)

    missing = [name for name in (WINDFOR_FILE, FUELHH_FILE) if not (directory / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"snapshot files missing in {directory}: {', '.join(missing)} "
            f"(run backend/scripts/fetch_elexon.py first)"
        )

    wf_path = directory / WINDFOR_FILE
    fh_path = directory / FUELHH_FILE

    forecasts = _read_jsonl_gz(wf_path)
    _require_keys(forecasts, ("start_time", "publish_time"), wf_path)

    actuals = _read_jsonl_gz(fh_path)
    _require_keys(actuals, ("start_time", "generation"), fh_path)

    meta_path = directory / "snapshot_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    # Nowhere else to honestly say this: the snapshot is the data this app presents.
    return {"forecasts": forecasts, "actuals": actuals, "meta": meta}


def actuals_by_start(snapshot: dict) -> dict:
    """{start_time str: generation float|None} — the shape `processing.match` consumes."""
    return {r["start_time"]: r["generation"] for r in snapshot["actuals"]}
