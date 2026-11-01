#!/usr/bin/env python3
"""One-off fetch of Elexon data for the January 2026 dashboard snapshot.

Downloads:
  - WINDFOR  (wind forecasts)  by publish window  2025-12-28T00:00Z -> 2026-02-01T00:00Z
  - FUELHH   (actuals, WIND)   by settlement date 2026-01-01     -> 2026-02-02

Saves:
  - data/raw/*.json          raw API responses, byte-for-byte, never modified
  - data/snapshot/*.json.gz  cleaned, normalised records (JSON lines, gzipped)
  - data/snapshot/snapshot_meta.json       fetch provenance + row counts
  - data/snapshot/inspection_report.json   raw-inspection checklist (file 02 §5)

The deployed app never calls Elexon at request time; it reads the snapshot.

Ground rules respected here:
  - Raw output first: nothing computed here goes in any document without being seen.
  - Missing is missing: null generation values are kept as null, never filled.
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"

ROOT = Path(__file__).resolve().parents[1]

# Standalone script: make the app package importable for the shared constants.
# app/config.py is the single source of truth for windows and chunking (file 01 §6).
sys.path.insert(0, str(ROOT))
from app.config import (  # noqa: E402
    CHUNK_DAYS,
    FETCH_FUELHH_SETTLEMENT_FROM as FUELHH_FROM,
    FETCH_FUELHH_SETTLEMENT_TO as FUELHH_TO,
    FETCH_WINDFOR_PUBLISH_FROM as WINDFOR_FROM,
    FETCH_WINDFOR_PUBLISH_TO as WINDFOR_TO,
    RAW_DIR,
    SNAPSHOT_DIR as SNAP_DIR,
)

# FUELHH keeps the latest known reading when the API returns duplicate startTimes:
# raw rows store publishTime; helper below compares those ISO strings directly.
WINDFOR_SNAPSHOT_FILE = "windfor.json.gz"
FUELHH_SNAPSHOT_FILE = "fuelhh_wind.json.gz"

MAX_ATTEMPTS = 6
INITIAL_BACKOFF_S = 2.0
MAX_BACKOFF_S = 60.0
TIMEOUT_S = 60


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_utc(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def chunked_datetimes(start: datetime, end: datetime, days: int):
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=days), end)
        yield cur, nxt
        cur = nxt


def chunked_dates(start: date, end: date, days: int):
    cur = start
    while cur <= end:
        nxt = min(cur + timedelta(days=days - 1), end)
        yield cur, nxt
        cur = nxt + timedelta(days=1)


def fail_fast(msg: str) -> None:
    sys.exit(f"FATAL: {msg}")


def fetch_with_retry(
    session: requests.Session, url: str, params: dict, label: str
) -> requests.Response:
    """GET with timeout; retry timeout/429/5xx with exponential backoff; fail fast otherwise."""
    delay = INITIAL_BACKOFF_S

    def retry(msg: str) -> None:
        print(f"  [{label}] {msg}; retrying in {delay:.0f}s")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = session.get(url, params=params, timeout=TIMEOUT_S)
        except requests.Timeout:
            retry("timeout")
        except requests.RequestException as exc:
            retry(f"{type(exc).__name__}: {exc}")
        else:
            if 200 <= resp.status_code < 300:
                return resp
            if resp.status_code == 429 or resp.status_code >= 500:
                retry(f"HTTP {resp.status_code}")
            else:
                fail_fast(
                    f"[{label}] HTTP {resp.status_code} fail-fast. Body: {resp.text[:500]}"
                )
        time.sleep(delay)
        delay = min(delay * 2, MAX_BACKOFF_S)
    fail_fast(f"[{label}] retried {MAX_ATTEMPTS} times without success")


def save_raw(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def fetch_windfor(session: requests.Session) -> tuple[list[dict], dict]:
    """Fetch WINDFOR by publish window in chunks. Returns (raw_rows, meta)."""
    url = f"{BASE_URL}/datasets/WINDFOR/stream"
    rows: list[dict] = []
    meta = {"dataset": "WINDFOR", "url": url, "chunks": []}
    for i, (from_dt, to_dt) in enumerate(chunked_datetimes(WINDFOR_FROM, WINDFOR_TO, CHUNK_DAYS), 1):
        label = f"WINDFOR chunk {i}"
        params = {
            "publishDateTimeFrom": iso_utc(from_dt),
            "publishDateTimeTo": iso_utc(to_dt),
        }
        resp = fetch_with_retry(session, url, params, label)
        save_raw(RAW_DIR / f"windfor_{i:02d}.json", resp.content)
        chunk_rows = resp.json()
        if not isinstance(chunk_rows, list):
            fail_fast(f"[{label}] expected a JSON array, got {type(chunk_rows).__name__}")
        rows.extend(chunk_rows)
        meta["chunks"].append(
            {
                "file": f"windfor_{i:02d}.json",
                **params,
                "rows": len(chunk_rows),
            }
        )
        print(f"  [{label}] {len(chunk_rows)} rows")
    return rows, meta


def fetch_fuelhh(session: requests.Session) -> tuple[list[dict], dict]:
    """Fetch FUELHH by settlement date in chunks (fuelType=WIND). Returns (raw_rows, meta)."""
    url = f"{BASE_URL}/datasets/FUELHH/stream"
    rows: list[dict] = []
    meta = {"dataset": "FUELHH", "url": url, "chunks": []}
    for i, (from_d, to_d) in enumerate(chunked_dates(FUELHH_FROM, FUELHH_TO, CHUNK_DAYS), 1):
        label = f"FUELHH chunk {i}"
        params = {
            "settlementDateFrom": from_d.isoformat(),
            "settlementDateTo": to_d.isoformat(),
            "fuelType": "WIND",
        }
        resp = fetch_with_retry(session, url, params, label)
        save_raw(RAW_DIR / f"fuelhh_{i:02d}.json", resp.content)
        chunk_rows = resp.json()
        if not isinstance(chunk_rows, list):
            fail_fast(f"[{label}] expected a JSON array, got {type(chunk_rows).__name__}")
        rows.extend(chunk_rows)
        meta["chunks"].append(
            {
                "file": f"fuelhh_{i:02d}.json",
                **params,
                "rows": len(chunk_rows),
            }
        )
        print(f"  [{label}] {len(chunk_rows)} rows")
    return rows, meta




def minute_of(ts: str | None) -> str | None:
    if not ts or len(ts) < 16:
        return None
    return ts[14:16]


def clock_of(ts: str | None) -> str | None:
    if not ts:
        return None
    return ts[:16][11:16]


def inspect(window_rows: dict, fuelhh_raw: list[dict], windfor_norm: list[dict], fuelhh_norm: list[dict]) -> dict:
    """Raw-inspection checklist from file 02 §5. Computed over RAW rows."""
    report: dict = {}

    for ds, rows in window_rows.items():
        start_times = [r.get("startTime") for r in rows if r.get("startTime")]
        pub_times = [r.get("publishTime") for r in rows if r.get("publishTime")]
        item = {
            "first_3_raw_rows": rows[:3],
            "row_count_raw": len(rows),
            "distinct_startTime_minutes": sorted({minute_of(t) for t in start_times}),
            "distinct_publishTime_clock_HHMM": sorted({clock_of(t) for t in pub_times}),
            "min_startTime": min(start_times) if start_times else None,
            "max_startTime": max(start_times) if start_times else None,
            "min_publishTime": min(pub_times) if pub_times else None,
            "max_publishTime": max(pub_times) if pub_times else None,
            "null_generation_count": sum(1 for r in rows if r.get("generation") is None),
        }
        if ds == "WINDFOR":
            item["rows_startTime_before_publishTime"] = sum(
                1
                for r in rows
                if r.get("startTime") and r.get("publishTime") and r["startTime"] < r["publishTime"]
            )
            keys = [(r.get("startTime"), r.get("publishTime")) for r in rows]
            item["duplicate_key_counts"] = {
                "keys": "(startTime, publishTime)",
                "total_rows": len(keys),
                "distinct_keys": len(set(keys)),
                "duplicate_rows": len(keys) - len(set(keys)),
            }
        else:  # FUELHH
            item["distinct_fuelType_values"] = sorted(
                {str(r.get("fuelType")) for r in rows} | {"WIND"}
            )
            fuel_types = {}
            for r in rows:
                ft = str(r.get("fuelType"))
                fuel_types[ft] = fuel_types.get(ft, 0) + 1
            item["fuelType_counts"] = fuel_types
            keys = [r.get("startTime") for r in rows]
            item["duplicate_key_counts"] = {
                "keys": "(startTime)",
                "total_rows": len(keys),
                "distinct_keys": len(set(keys)),
                "duplicate_rows": len(keys) - len(set(keys)),
            }
        report[ds] = item
    return report




def normalise_windfor(rows: list[dict]) -> tuple[list[dict], dict]:
    """Raw WINDFOR rows -> snapshot records. Dedupes identical (startTime, publishTime)."""
    records: dict[tuple[str, str], dict] = {}
    conflicts = 0
    missing_required_keys = 0
    for r in rows:
        required = ("startTime", "publishTime", "generation")
        if any(key not in r for key in required):
            missing_required_keys += 1
            continue
        st, pt, gen = r["startTime"], r["publishTime"], r["generation"]
        if not st or not pt:
            missing_required_keys += 1
            continue
        key = (st, pt)
        if key in records:
            old = records[key]["generation"]
            if old != gen:
                conflicts += 1
                records[key] = {"start_time": st, "publish_time": pt, "generation": gen}
            continue
        records[key] = {"start_time": st, "publish_time": pt, "generation": gen}
    out = [records[k] for k in sorted(records)]
    return out, {
        "rows_raw": len(rows),
        "rows_snapshot": len(out),
        "rows_missing_required_keys": missing_required_keys,
        "conflicting_duplicates": conflicts,
    }


def normalise_fuelhh(rows: list[dict]) -> tuple[list[dict], dict]:
    """Raw FUELHH rows -> snapshot records. WIND only; keeps latest publishTime per startTime."""
    non_wind = sum(1 for r in rows if str(r.get("fuelType", "")).upper() != "WIND")
    if non_wind:
        # defence in depth: the API filter should have removed these
        print(f"  [FUELHH] WARNING: {non_wind} non-WIND rows present in API response")
    latest: dict[str, dict] = {}
    missing_required_keys = 0
    for r in rows:
        if str(r.get("fuelType", "")).upper() != "WIND":
            continue
        if "startTime" not in r or "generation" not in r:
            missing_required_keys += 1
            continue
        st, pt, gen = r["startTime"], r.get("publishTime"), r["generation"]
        if not st:
            missing_required_keys += 1
            continue
        prior = latest.get(st)
        if prior is None or (pt or "") >= (prior["generation_ts"] or ""):
            latest[st] = {"start_time": st, "generation": gen, "generation_ts": pt}
    out = [{"start_time": v["start_time"], "generation": v["generation"]} for v in latest.values()]
    out.sort(key=lambda r: r["start_time"])
    return out, {
        "rows_raw": len(rows),
        "non_wind_discarded": non_wind,
        "rows_missing_required_keys": missing_required_keys,
        "rows_snapshot": len(out),
    }




def write_jsonl_gz(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(json.dumps(r, separators=(",", ":")) for r in records)
    with gzip.open(path, "wb") as fh:
        fh.write(lines.encode("utf-8"))


def main() -> None:
    print(f"Fetch start: {utc_now_iso()}")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SNAP_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    print("Fetching WINDFOR (forecasts)...")
    windfor_raw, windfor_meta = fetch_windfor(session)
    print(f"WINDFOR raw rows: {len(windfor_raw)}")

    print("Fetching FUELHH (actuals, WIND)...")
    fuelhh_raw, fuelhh_meta = fetch_fuelhh(session)
    print(f"FUELHH raw rows: {len(fuelhh_raw)}")

    print("Normalising...")
    windfor_norm, wf_norm_meta = normalise_windfor(windfor_raw)
    fuelhh_norm, fh_norm_meta = normalise_fuelhh(fuelhh_raw)
    print(f"WINDFOR snapshot records: {len(windfor_norm)}")
    print(f"FUELHH snapshot records: {len(fuelhh_norm)}")

    print("Building inspection report (file 02 section 5)...")
    report = inspect(
        {"WINDFOR": windfor_raw, "FUELHH": fuelhh_raw}, fuelhh_raw, windfor_norm, fuelhh_norm
    )
    (SNAP_DIR / "inspection_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("Writing snapshot...")
    write_jsonl_gz(SNAP_DIR / WINDFOR_SNAPSHOT_FILE, windfor_norm)
    write_jsonl_gz(SNAP_DIR / FUELHH_SNAPSHOT_FILE, fuelhh_norm)

    meta = {
        "fetched_at_utc": utc_now_iso(),
        "base_url": BASE_URL,
        "windows": {
            "windfor_publish": {"from": iso_utc(WINDFOR_FROM), "to": iso_utc(WINDFOR_TO)},
            "fuelhh_settlement": {"from": FUELHH_FROM.isoformat(), "to": FUELHH_TO.isoformat()},
        },
        "row_counts": {
            "windfor_raw": wf_norm_meta,
            "fuelhh_raw": fh_norm_meta,
        },
        "datasets": [windfor_meta, fuelhh_meta],
        "snapshot_files": [WINDFOR_SNAPSHOT_FILE, FUELHH_SNAPSHOT_FILE],
    }
    (SNAP_DIR / "snapshot_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print("Print checklist from inspection report:")
    insp = report
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "first_3_raw_rows"} for k, v in insp.items()}, indent=2))
    print("First 3 raw WINDFOR rows:")
    print(json.dumps(insp["WINDFOR"]["first_3_raw_rows"], indent=2))
    print("First 3 raw FUELHH rows:")
    print(json.dumps(insp["FUELHH"]["first_3_raw_rows"], indent=2))

    print(f"Fetch done: {utc_now_iso()}")


if __name__ == "__main__":
    main()
