# -*- coding: utf-8 -*-
"""In-memory snapshot store. The ONLY module that reads the snapshot.

The deployed app never calls Elexon at request time — it serves the frozen
January-2026 snapshot committed in data/snapshot/. Loads fail fast with a clear
message if snapshot files are missing or malformed. The env var SNAPSHOT_DIR
overrides the default directory (the contract tests use it to point at a tiny
fixture snapshot).
"""

from __future__ import annotations

import gzip
import json
import math
import os
from pathlib import Path

from . import config, timeutil

WINDFOR_FILE = "windfor.json.gz"
FUELHH_FILE = "fuelhh_wind.json.gz"  # WIND-only rows (filtered at fetch time)


def _snapshot_dir(override: Path | str | None) -> Path:
    """Explicit argument wins, then the SNAPSHOT_DIR env var, then the default."""
    if override is not None:
        return Path(override)
    return Path(os.environ.get("SNAPSHOT_DIR", str(config.SNAPSHOT_DIR)))


def _read_jsonl_gz(path: Path) -> list[dict]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
    except (OSError, EOFError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"malformed snapshot file {path.name}: {exc}") from exc


def _require_keys(records: list[dict], keys: tuple[str, ...], path: Path) -> None:
    for index, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise ValueError(
                f"malformed snapshot file {path.name}: row {index} must be an object"
            )
        for key in keys:
            if key not in rec:
                raise ValueError(
                    f"malformed snapshot file {path.name}: row {index} missing {key!r}"
                )


def _validate_records(
    records: list[dict],
    path: Path,
    timestamp_fields: tuple[str, ...],
) -> None:
    for index, rec in enumerate(records):
        for field in timestamp_fields:
            try:
                timeutil.parse_utc(rec[field])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"malformed snapshot file {path.name}: row {index} has invalid {field}: {exc}"
                ) from exc

        generation = rec["generation"]
        if generation is not None and (
            isinstance(generation, bool)
            or not isinstance(generation, (int, float))
            or not math.isfinite(generation)
        ):
            raise ValueError(
                f"malformed snapshot file {path.name}: row {index} has invalid generation; "
                "expected a finite number or null"
            )


def load_snapshot(data_dir: Path | str | None = None) -> dict:
    """Return {'forecasts', 'actuals', 'meta'} from the snapshot. Misspelled or
    truncated files raise immediately — never load half a snapshot.

    Normalised shapes:
      forecasts: {"start_time", "publish_time", "generation"}   (all WINDFOR versions,
                 nulls kept as None — missing stays missing, never filled)
      actuals:   {"start_time", "generation"}                   (WIND only, WIND-ness
                 verified 100% in the fetch script)
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
    _require_keys(forecasts, ("start_time", "publish_time", "generation"), wf_path)
    _validate_records(forecasts, wf_path, ("start_time", "publish_time"))

    actuals = _read_jsonl_gz(fh_path)
    _require_keys(actuals, ("start_time", "generation"), fh_path)
    _validate_records(actuals, fh_path, ("start_time",))

    meta_path = directory / "snapshot_meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"malformed snapshot metadata {meta_path.name}: {exc}") from exc
    if not isinstance(meta, dict):
        raise ValueError(f"malformed snapshot metadata {meta_path.name}: expected an object")

    return {"forecasts": forecasts, "actuals": actuals, "meta": meta}


def actuals_by_start(snapshot: dict) -> dict:
    """{start_time str: generation float|None} — the shape `processing.match` consumes."""
    return {r["start_time"]: r["generation"] for r in snapshot["actuals"]}
