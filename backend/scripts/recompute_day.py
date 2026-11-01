# -*- coding: utf-8 -*-
"""Independent single-day recompute (verify-the-verifier script).

Recomputes one decision day — as-of selection, matching, metrics — directly
from the snapshot, WITHOUT importing anything from the app package. Plain
loops, stdlib only (gzip, json, argparse, urllib). If the app were ever wrong,
this script is the second, independent opinion.

Usage:
    python scripts/recompute_day.py 2026-01-05 09:00
    python scripts/recompute_day.py 2026-01-05 09:00 --server https://<app-host>

With --server, the script ALSO fetches the app's own /api/forecast-vs-actual
response and prints both answers side by side; without it, only local
recomputation is printed. Exit code 0 when both (if present) agree, 1 otherwise.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
DATE_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_date(text: str) -> datetime:
    if not DATE_SHAPE.match(text):
        raise SystemExit(f"bad decision date (expected YYYY-MM-DD): {text!r}")
    return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=UTC)


def _parse_hhmm(text: str) -> tuple[int, int]:
    parts = str(text).split(":")
    good = (
        len(parts) == 2
        and all(p.isdigit() and len(p) == 2 for p in parts)
        and 0 <= int(parts[0]) <= 23
        and 0 <= int(parts[1]) <= 59
    )
    if not good:
        raise SystemExit(f"bad cutoff (expected HH:MM): {text!r}")
    return int(parts[0]), int(parts[1])


def _parse_utc(text: str) -> datetime:
    dt = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SystemExit(f"naive timestamp rejected (no offset): {text!r}")
    return dt.astimezone(UTC)


def load_snapshot(directory: Path) -> tuple[list[dict], list[dict]]:
    wf = directory / "windfor.json.gz"
    fh = directory / "fuelhh_wind.json.gz"
    missing = [p for p in (wf, fh) if not p.exists()]
    if missing:
        raise SystemExit(f"snapshot files missing: {', '.join(p.name for p in missing)} in {directory}")

    def read(path: Path) -> list[dict]:
        with gzip.open(path, "rt", encoding="utf-8") as fh_in:
            return [json.loads(line) for line in fh_in if line.strip()]

    return read(wf), read(fh)


def recompute(decision_date: str, hhmm: str, forecasts: list[dict], actuals: list[dict]) -> dict:
    """Everything the app computes for one day, built independently here."""
    d = _parse_date(decision_date)
    h, m = _parse_hhmm(hhmm)
    cutoff = d + timedelta(hours=h, minutes=m)
    win_start = d + timedelta(days=1)
    win_end = win_start + timedelta(days=1)

    # 1) selection: latest version published at or before the cutoff wins.
    #    startIndex in the window only; inclusive cutoff; last duplicate wins.
    versions: dict[tuple[datetime, datetime], float | None] = {}
    expected_starts: set[datetime] = set()
    for row in forecasts:
        st = _parse_utc(row["start_time"])
        pt = _parse_utc(row["publish_time"])
        if not (win_start <= st < win_end):
            continue
        expected_starts.add(st)
        if pt > cutoff:
            continue
        versions[(st, pt)] = row["generation"]

    chosen: dict[datetime, tuple[datetime, float | None]] = {}
    for (st, pt), gen in versions.items():
        prior = chosen.get(st)
        if prior is None or pt > prior[0]:
            chosen[st] = (pt, gen)

    expected = len(expected_starts)

    # 2) matching on identical startTime, nulls stay null, never zero.
    actual_lookup = {_parse_utc(a["start_time"]): a["generation"] for a in actuals}
    errors: list[float] = []
    matched = 0
    for st in sorted(chosen):
        gen, actual = chosen[st][1], actual_lookup.get(st)
        if gen is not None and actual is not None:
            matched += 1
            errors.append(gen - actual)

    # 3) metrics over matched, non-null errors only.
    if errors:
        n = len(errors)
        bias = sum(errors) / n
        mae = sum(abs(e) for e in errors) / n
        rmse = math.sqrt(sum(e * e for e in errors) / n)
        ranks = sorted(abs(e) for e in errors)
        pos = 0.9 * (n - 1)
        lo, hi = math.floor(pos), math.ceil(pos)
        p90 = ranks[lo] if lo == hi else ranks[lo] + (pos - lo) * (ranks[hi] - ranks[lo])
        metrics = {"n": n, "bias_mw": bias, "mae_mw": mae, "rmse_mw": rmse,
                   "p90_abs_error_mw": p90, "max_abs_error_mw": ranks[-1]}
    else:
        metrics = {"n": 0, "bias_mw": None, "mae_mw": None, "rmse_mw": None,
                   "p90_abs_error_mw": None, "max_abs_error_mw": None}

    return {
        "decision_date": decision_date,
        "cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "delivery_day": win_start.date().isoformat(),
        "expected_points": expected,
        "matched_points": matched,
        "coverage_pct": (matched / expected) * 100.0 if expected else 0.0,
        "metrics": metrics,
    }


def fetch_server(base_url: str, decision_date: str, hhmm: str) -> dict:
    url = f"{base_url.rstrip('/')}/api/forecast-vs-actual?decision_date={decision_date}&cutoff={hhmm}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read())


def comparison_differences(mine: dict, theirs: dict) -> list[str]:
    """Compare every decision-level field and metric reported by the script."""
    differences = []
    for key in (
        "decision_date", "cutoff_utc", "delivery_day", "expected_points", "matched_points"
    ):
        if mine[key] != theirs[key]:
            differences.append(f"{key}: recompute={mine[key]!r}, server={theirs[key]!r}")

    local_metrics = {**mine["metrics"], "expected": mine["expected_points"],
                     "coverage_pct": mine["coverage_pct"]}
    remote_metrics = theirs["metrics"]
    metric_keys = (
        "n", "expected", "coverage_pct", "bias_mw", "mae_mw", "rmse_mw",
        "p90_abs_error_mw", "max_abs_error_mw",
    )
    for key in metric_keys:
        local, remote = local_metrics[key], remote_metrics[key]
        if local is None or remote is None:
            same = local is remote
        else:
            same = round(local, 3) == round(remote, 3)
        if not same:
            differences.append(f"metrics.{key}: recompute={local!r}, server={remote!r}")
    return differences


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute one decision day independently of the app.")
    parser.add_argument("decision_date", help="decision date, YYYY-MM-DD")
    parser.add_argument("cutoff", nargs="?", default="09:00", help="cutoff HH:MM on the decision date")
    parser.add_argument("--server", default=None, help="base URL of the running app to compare against")
    parser.add_argument("--snapshot", default=None, help="snapshot directory (default: backend/data/snapshot)")
    args = parser.parse_args()

    directory = Path(args.snapshot) if args.snapshot else Path(__file__).resolve().parents[1] / "data" / "snapshot"
    forecasts, actuals = load_snapshot(directory)
    mine = recompute(args.decision_date, args.cutoff, forecasts, actuals)

    m = mine["metrics"]
    print(f"recomputed from snapshot at {directory}")
    print(f"  decision_date    {mine['decision_date']}")
    print(f"  cutoff_utc       {mine['cutoff_utc']}")
    print(f"  delivery_day     {mine['delivery_day']}")
    print(f"  matched/expected {mine['matched_points']}/{mine['expected_points']}  (coverage {mine['coverage_pct']:.3f}%)")
    print(f"  bias_mw          {m['bias_mw']:.3f}" if m["bias_mw"] is not None else "  bias_mw          -")
    print(f"  mae_mw           {m['mae_mw']:.3f}" if m["mae_mw"] is not None else "  mae_mw           -")
    print(f"  rmse_mw          {m['rmse_mw']:.3f}" if m["rmse_mw"] is not None else "  rmse_mw          -")
    print(f"  p90_abs_error_mw {m['p90_abs_error_mw']:.3f}" if m["p90_abs_error_mw"] is not None else "  p90_abs_error_mw -")
    print(f"  max_abs_error_mw {m['max_abs_error_mw']:.3f}" if m["max_abs_error_mw"] is not None else "  max_abs_error_mw -")

    if not args.server:
        return 0

    theirs = fetch_server(args.server, args.decision_date, args.cutoff)
    tm = theirs["metrics"]
    print(f"\nserver {args.server}")
    print(f"  decision_date    {theirs['decision_date']}")
    print(f"  cutoff_utc       {theirs['cutoff_utc']}")
    print(f"  delivery_day     {theirs['delivery_day']}")
    print(f"  matched/expected {theirs['matched_points']}/{theirs['expected_points']}")
    for key in (
        "n", "expected", "coverage_pct", "bias_mw", "mae_mw", "rmse_mw",
        "p90_abs_error_mw", "max_abs_error_mw",
    ):
        value = tm[key]
        rendered = "-" if value is None else f"{value:.3f}"
        print(f"  {key:<17} {rendered}")

    differences = comparison_differences(mine, theirs)
    for difference in differences:
        print(f"  MISMATCH {difference}")
    print("\nMATCH: recompute agrees with all reported metrics" if not differences
          else "\nMISMATCH: recompute disagrees with the server")
    return 0 if not differences else 1


if __name__ == "__main__":
    sys.exit(main())
