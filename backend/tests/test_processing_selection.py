# -*- coding: utf-8 -*-
"""Selection tests S1-S9 plus series glue (file 07 §1).

Fixtures are hand-made with HYPOTHETICAL numbers from file 03 §5 — not live data.
Delivery interval D 10:00Z on delivery day 2026-01-16, decision day 2026-01-15.
"""

from __future__ import annotations

import math
import random

from app import processing as P
from app.timeutil import parse_utc

D = "2026-01-15"                       # decision day (delivery day = 2026-01-16)
WIN = ("2026-01-16T00:00:00Z", "2026-01-17T00:00:00Z")
T10 = "2026-01-16T10:00:00Z"           # the reference delivery interval

# file 03 §5 versions for T10 (HYPOTHETICAL); "D-1" = 2026-01-15, "D-2" = 2026-01-14
V230 = ("2026-01-14T22:30:00Z", 5000)  # D-2 22:30Z
V430 = ("2026-01-15T04:30:00Z", 5500)  # D-1 04:30Z
V730 = ("2026-01-15T07:30:00Z", 5200)  # D-1 07:30Z
V930 = ("2026-01-15T09:30:00Z", 4800)  # D-1 09:30Z — published after the 09:00 cutoff

CUT900 = "2026-01-15T09:00:00Z"


def fc(st: str, pt: str, gen):
    return {"start_time": st, "publish_time": pt, "generation": gen}


def versions_base():
    return [fc(T10, V230[0], V230[1]),
            fc(T10, V430[0], V430[1]),
            fc(T10, V730[0], V730[1]),
            fc(T10, V930[0], V930[1])]


def select(forecasts, cutoff=CUT900):
    return P.select_as_of(forecasts, cutoff, *WIN)


def chosen_gen(chosen, st=T10):
    rec = chosen.get(parse_utc(st))
    return None if rec is None else rec["generation"]


def chosen_pub(chosen, st=T10):
    return chosen[parse_utc(st)]["publish_time"].strftime("%H:%M")


# ---------------------------------------------------------------- selection

def test_s1_latest_eligible_wins():
    chosen = select(versions_base())
    assert chosen_pub(chosen) == "07:30"
    assert chosen_gen(chosen) == 5200          # 09:30 run excluded: after cutoff


def test_s2_version_exactly_at_cutoff_included():
    chosen = select(versions_base() + [fc(T10, CUT900, 4900)])
    assert chosen_pub(chosen) == "09:00"       # inclusive boundary (file 03 §5)
    assert chosen_gen(chosen) == 4900


def test_s3_one_second_after_cutoff_excluded():
    chosen = select(versions_base() + [fc(T10, "2026-01-15T09:00:01Z", 4900)])
    assert chosen_pub(chosen) == "07:30"
    assert chosen_gen(chosen) == 5200


def test_s4_all_versions_after_cutoff_no_forecast():
    after = versions_base()[:3]                # drop the 07:30, keep the rest after-cut
    after = [r for r in after if parse_utc(r["publish_time"]) > parse_utc(CUT900)]
    after += [fc(T10, V930[0], V930[1])]
    chosen = select(after)
    assert parse_utc(T10) not in chosen        # missing means missing — not zero


def test_s5_latest_eligible_null_is_missing_no_fallback():
    rows = [fc(T10, V230[0], V230[1]), fc(T10, V430[0], 5500), fc(T10, V730[0], None)]
    chosen = select(rows)
    rec = chosen[parse_utc(T10)]
    assert rec["generation"] is None           # stays with the newest eligible version
    # and matching must NOT quietly reach for the older 5500 run


def test_s6_starttime_outside_window_ignored():
    rows = versions_base() + [fc("2026-01-15T10:00:00Z", V730[0], 5210)]
    assert parse_utc("2026-01-15T10:00:00Z") not in select(rows)


def test_s7_duplicate_identical_rows_counted_once():
    chosen = select(versions_base() + [fc(T10, V730[0], V730[1])])
    assert len(chosen) == 1
    assert chosen_gen(chosen) == 5200


def test_s8_different_cutoffs_different_versions():
    c08 = select(versions_base(), cutoff="2026-01-15T08:00:00Z")
    c10 = select(versions_base(), cutoff="2026-01-15T10:00:00Z")
    assert chosen_pub(c08) == "07:30"          # 09:30 run not yet known at 08:00
    assert chosen_pub(c10) == "09:30"          # now it is — selection MUST move
    assert chosen_gen(c10) == 4800


def test_s9_leakage_property_random_fixtures():
    """No cutoff choice may ever surface a version published after it."""
    rng = random.Random(20260131)
    for _ in range(25):
        rows, n = [], rng.randint(1, 6)
        for i in range(n):
            hh = rng.randint(0, 23)
            mm = rng.choice([0, 30])
            pub_day = "2026-01-15" if rng.random() < 0.4 else "2026-01-14"
            pt = f"{pub_day}T{hh:02d}:{mm:02d}:00Z"
            rows.append(fc(T10, pt, rng.randint(0, 20000)))
        cut = rng.choice(["2026-01-14T22:00:00Z", "2026-01-15T06:00:00Z",
                          "2026-01-15T09:00:00Z", "2026-01-15T12:00:00Z"])
        chosen = select(rows, cutoff=cut)
        cut_dt = parse_utc(cut)
        for rec in chosen.values():
            assert rec["publish_time"] <= cut_dt   # leak test: ALWAYS true


# ---------------------------------------------------------------- series glue

def test_series_shape_and_metrics_glue():
    act = {parse_utc(T10): 4700.0}
    # full 24-hour product grid from one 07:30 run, like the real snapshot
    # (hour 10 comes from versions_base() itself; grid must not re-publish it)
    grid = [
        fc(f"2026-01-16T{h:02d}:00:00Z", V730[0], 4000)
        for h in range(24)
        if h != 10
    ]
    s = P.as_of_series(D, "09:00", versions_base() + grid, act)
    assert s["decision_date"] == "2026-01-15"
    assert s["delivery_day"] == "2026-01-16"
    assert s["cutoff_utc"] == "2026-01-15T09:00:00Z"
    assert s["expected_points"] == 24                          # hourly product grid
    assert s["matched_points"] == 1
    pt = next(p for p in s["points"] if p["start_time"] == "2026-01-16T10:00:00Z")
    assert pt["error_mw"] == 500 and pt["lead_time_h"] == 26.5  # file 03 §5 worked example
    assert s["metrics"]["mae_mw"] == 500
    assert math.isclose(s["metrics"]["coverage_pct"], 100.0 / 24)


def test_series_empty_delivery_day_is_not_error():
    s = P.as_of_series("2026-01-20", "09:00", [], {})
    assert s["points"] == [] and s["matched_points"] == 0
    assert s["metrics"]["n"] == 0 and s["metrics"]["mae_mw"] is None
    assert s["metrics"]["coverage_pct"] == 0.0
