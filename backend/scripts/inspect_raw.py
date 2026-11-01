#!/usr/bin/env python3
"""Stage 1 inspection: small Elexon requests, facts printed to the terminal.

Read-only tool (no files written): a few days of each dataset inside the fetch
windows, plus a range-limit probe. The full-window snapshot fetch lives in
fetch_elexon.py; this script exists so the Stage 1 checklist (file 02 §5) can be
re-run and re-verified at any time without touching the snapshot.

Printed facts per checklist (Stage 1):
  exact URL + HTTP status, first 3 raw rows per dataset, distinct fuelType values
  BEFORE filtering, distinct startTime minutes, distinct WINDFOR publish HH:MM,
  null-generation counts, duplicate counts, min/max startTime & publishTime,
  WINDFOR rows with startTime < publishTime, max lead time in hours, and whether
  date-range limits force chunking (probe: try a longer range, print error body).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import requests

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
TIMEOUT_S = 60

# Small in-window probes (NOT the fetch windows; processing enforces exact limits).
WINDFOR_PUBLISH_FROM = datetime(2026, 1, 6, 0, 0, tzinfo=timezone.utc)
WINDFOR_PUBLISH_TO = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
FUELHH_FROM = date(2026, 1, 6)
FUELHH_TO = date(2026, 1, 9)
# Range-limit probe: one request over a LONG range to see if the endpoint errors.
PROBE_PUBLISH_FROM = datetime(2025, 12, 1, 0, 0, tzinfo=timezone.utc)
PROBE_PUBLISH_TO = datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def clock_of(ts: str | None) -> str | None:
    return ts[:16][11:16] if ts else None


def minute_of(ts: str | None) -> str | None:
    return ts[14:16] if ts and len(ts) >= 16 else None


def lead_hours(row: dict) -> float | None:
    st, pt = row.get("startTime"), row.get("publishTime")
    if not st or not pt:
        return None
    start = datetime.fromisoformat(st.replace("Z", "+00:00"))
    pub = datetime.fromisoformat(pt.replace("Z", "+00:00"))
    return (start - pub).total_seconds() / 3600.0


def get(session: requests.Session, dataset: str, params: dict, label: str) -> tuple[int, object | str]:
    url = f"{BASE_URL}/datasets/{dataset}/stream"
    resp = session.get(url, params=params, timeout=TIMEOUT_S)
    print(f"[{label}] GET {url} -> HTTP {resp.status_code}")
    print(f"[{label}] params: {params}")
    if 200 <= resp.status_code < 300:
        return resp.status_code, resp.json()
    print(f"[{label}] error body: {resp.text[:500]}")
    return resp.status_code, resp.text


def inspect_dataset(label: str, rows: list[dict], windfor: bool) -> None:
    start_times = [r.get("startTime") for r in rows if r.get("startTime")]
    pub_times = [r.get("publishTime") for r in rows if r.get("publishTime")]
    print(f"\n===== {label} =====")
    print(f"rows: {len(rows)}")
    print(f"first 3 raw rows: {rows[:3]}")
    print(f"distinct startTime minutes: {sorted({minute_of(t) for t in start_times})}")
    print(f"distinct publishTime HH:MM (WINDFOR): {sorted({clock_of(t) for t in pub_times})}")
    print(f"null generation count: {sum(1 for r in rows if r.get('generation') is None)}")
    print(f"min startTime: {min(start_times) if start_times else None}")
    print(f"max startTime: {max(start_times) if start_times else None}")
    print(f"min publishTime: {min(pub_times) if pub_times else None}")
    print(f"max publishTime: {max(pub_times) if pub_times else None}")
    if windfor:
        before = sum(
            1 for r in rows
            if r.get("startTime") and r.get("publishTime") and r["startTime"] < r["publishTime"]
        )
        keys = [(r.get("startTime"), r.get("publishTime")) for r in rows]
        leads = [h for h in (lead_hours(r) for r in rows) if h is not None]
        print(f"rows with startTime < publishTime: {before} (normal: forecasts for future)")
        print(f"duplicates on (startTime, publishTime): {len(keys) - len(set(keys))}")
        positive = [h for h in leads if h > 0]
        print(f"max lead time (startTime - publishTime): {max(positive) if positive else None} h "
              f"(only positive leads considered)")
    else:
        keys = [r.get("startTime") for r in rows]
        print(f"distinct fuelType values (response as fetched): "
              f"{sorted({str(r.get('fuelType')) for r in rows})}")
        print(f"duplicates on startTime (after WIND filter): {len(keys) - len(set(keys))}")


def main() -> None:
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    # FUELHH WITHOUT the fuelType filter, so 'distinct fuelType BEFORE filtering' is honest.
    status, unfiltered = get(
        session, "FUELHH",
        {"settlementDateFrom": FUELHH_FROM.isoformat(), "settlementDateTo": FUELHH_FROM.isoformat()},
        "FUELHH unfiltered (1 day probe)",
    )
    if isinstance(unfiltered, list) and unfiltered:
        print(f"distinct fuelType values BEFORE filtering: "
              f"{sorted({str(r.get('fuelType')) for r in unfiltered})}")

    status, windfor = get(
        session, "WINDFOR",
        {"publishDateTimeFrom": iso(WINDFOR_PUBLISH_FROM), "publishDateTimeTo": iso(WINDFOR_PUBLISH_TO)},
        "WINDFOR probe",
    )
    status, fuelhh = get(
        session, "FUELHH",
        {"settlementDateFrom": FUELHH_FROM.isoformat(), "settlementDateTo": FUELHH_TO.isoformat(),
         "fuelType": "WIND"},
        "FUELHH probe",
    )

    if isinstance(windfor, list):
        inspect_dataset("WINDFOR probe", windfor, windfor=True)
    if isinstance(fuelhh, list):
        inspect_dataset("FUELHH probe (WIND filter applied)", fuelhh, windfor=False)

    # Range-limit probe: does a long publish window error out (forcing chunking)?
    status, body = get(
        session, "WINDFOR",
        {"publishDateTimeFrom": iso(PROBE_PUBLISH_FROM), "publishDateTimeTo": iso(PROBE_PUBLISH_TO)},
        "WINDFOR long-range probe",
    )
    print(f"\n[long-range probe] status {status}; "
          f"{'errored' if not isinstance(body, list) else f'succeeded with {len(body)} rows'} "
          f"-> chunking {'REQUIRED' if not isinstance(body, list) else 'not forced at this range'}")


if __name__ == "__main__":
    main()
