# -*- coding: utf-8 -*-
"""API contract tests (file 07 §4, Stage 4 STOP GATE list).

FastAPI TestClient against the app WITH the tiny fixture snapshot (SNAPSHOT_DIR
override in conftest). Every contract-example number below is HYPOTHETICAL.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

CUTOFF_UTC = "2026-01-15T09:00:00Z"  # fixture decision cutoff, full ISO form
DAY = "/api/forecast-vs-actual?decision_date=2026-01-15&cutoff=09:00"


def _ok(url: str) -> dict:
    resp = client.get(url)
    assert resp.status_code == 200, f"{url} -> {resp.status_code}: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------- health + config

def test_health_exact():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_config_key_set_exactly():
    cfg = _ok("/api/config")
    assert set(cfg) == {
        "decision_dates", "delivery_dates", "default_cutoff_utc",
        "cutoff_options_utc", "timezone_note", "snapshot_fetched_at",
    }
    assert set(cfg["decision_dates"]) == {"from", "to"}      # serialised by ALIAS
    assert set(cfg["delivery_dates"]) == {"from", "to"}
    assert cfg["default_cutoff_utc"] == "09:00"
    assert cfg["cutoff_options_utc"] == ["06:00", "08:00", "09:00", "10:00", "12:00"]
    assert cfg["snapshot_fetched_at"] == "2026-10-30T17:34:55Z"


# ---------------------------------------------------------------- forecast-vs-actual

def test_day_response_key_set_exactly():
    day = _ok(DAY)
    assert set(day) == {
        "decision_date", "cutoff_utc", "delivery_day", "expected_points",
        "matched_points", "points", "actuals_only", "metrics",
    }


def test_day_point_and_actual_key_sets_exactly():
    day = _ok(DAY)
    (first, *_rest) = day["points"]
    assert set(first) == {
        "start_time", "forecast_mw", "actual_mw", "publish_time",
        "lead_time_h", "error_mw", "matched",
    }
    for actual in day["actuals_only"]:
        assert set(actual) == {"start_time", "actual_mw"}


def test_day_metrics_key_set_exactly():
    metrics = _ok(DAY)["metrics"]
    assert set(metrics) == {
        "n", "expected", "coverage_pct", "bias_mw", "mae_mw",
        "rmse_mw", "p90_abs_error_mw", "max_abs_error_mw",
    }


def test_no_leakage_at_http_layer():
    """Every non-null publish_time in the response is at or before cutoff_utc."""
    day = _ok(DAY)
    for point in day["points"]:
        if point["publish_time"] is not None:
            assert point["publish_time"] <= day["cutoff_utc"]


def test_matched_points_consistency():
    day = _ok(DAY)
    matched = sum(1 for p in day["points"] if p["matched"] is True)
    assert day["matched_points"] == matched
    assert day["expected_points"] >= day["matched_points"]


def test_null_forecast_interval_never_zero():
    """hour 11: latest eligible version has NULL generation — must stay null."""
    day = _ok(DAY)
    (hour11,) = [p for p in day["points"] if p["start_time"] == "2026-01-16T11:00:00Z"]
    assert hour11["forecast_mw"] is None
    assert hour11["matched"] is False
    assert hour11["error_mw"] is None


def test_metrics_rounded_to_3dp():
    metrics = _ok(DAY)["metrics"]
    assert metrics["n"] == 2 and metrics["expected"] == 3
    for key in ("bias_mw", "coverage_pct"):
        value = metrics[key]
        assert value == round(value, 3)


def test_halfhour_actual_only_never_in_points():
    day = _ok(DAY)
    assert {"start_time": "2026-01-16T10:30:00Z", "actual_mw": 4690.0} in day["actuals_only"]
    assert all(p["start_time"] != "2026-01-16T10:30:00Z" for p in day["points"])


# ---------------------------------------------------------------- forecast-versions

def test_versions_key_set_exactly_one_selected():
    versions = _ok(
        "/api/forecast-versions?target_time=2026-01-16T10:00:00Z&cutoff=2026-01-15T09:00:00Z"
    )
    assert set(versions) == {"target_time", "cutoff_utc", "versions"}
    entries = versions["versions"]
    assert entries == sorted(entries, key=lambda v: v["publish_time"])  # ascending
    assert sum(1 for v in entries if v["selected"]) == 1                # exactly one
    for v in entries:
        assert set(v) == {
            "publish_time", "forecast_mw", "lead_time_h",
            "available_at_cutoff", "selected",
        }
        if not v["available_at_cutoff"]:
            assert v["publish_time"] > CUTOFF_UTC
    selected = next(v for v in entries if v["selected"])
    assert selected["publish_time"] == "2026-01-15T07:30:00Z"      # latest available
    assert selected["forecast_mw"] == 5200.0


def test_versions_outside_window_is_400_with_string_detail():
    resp = client.get(
        "/api/forecast-versions?target_time=2026-03-01T10:00:00Z&cutoff=2026-02-28T09:00:00Z"
    )
    assert resp.status_code == 400
    assert isinstance(resp.json()["detail"], str)


def test_versions_malformed_cutoff_is_4xx_string_detail():
    resp = client.get(
        "/api/forecast-versions?target_time=2026-01-16T10:00:00Z&cutoff=9am"
    )
    assert 400 <= resp.status_code < 500
    assert isinstance(resp.json()["detail"], str)


# ---------------------------------------------------------------- pooled + daily

def test_pooled_metrics_keys_and_pooled_not_averaged():
    pooled = _ok("/api/metrics?from=2026-01-01&to=2026-01-31&cutoff=09:00")
    assert set(pooled) == {
        "n", "expected", "coverage_pct", "bias_mw", "mae_mw",
        "rmse_mw", "p90_abs_error_mw", "max_abs_error_mw",
    }
    # Pooled n and math come from the fixture's only day with data;
    # Expected points are the three distinct WINDFOR start times in the fixture.
    assert pooled["n"] == 2
    assert pooled["expected"] == 3
    assert pooled["mae_mw"] == 2750.0          # errors [500, 5000] — NOT averaged daily


def test_pooled_n_equals_sum_of_daily_n():
    daily = _ok("/api/metrics/daily?cutoff=09:00")
    pooled = _ok("/api/metrics?from=2026-01-01&to=2026-01-31&cutoff=09:00")
    assert isinstance(daily, list) and len(daily) == 31        # one row per decision date
    for row in daily:
        assert set(row) == {
            "decision_date", "delivery_day", "n", "bias_mw", "mae_mw",
            "rmse_mw", "p90_abs_error_mw", "coverage_pct",
        }
    daily_n = sum(row["n"] for row in daily)
    assert pooled["n"] == daily_n


# ---------------------------------------------------------------- lead time

def test_lead_time_keys_and_open_bucket():
    buckets = _ok("/api/metrics/by-lead-time?bucket_hours=6")
    for bucket in buckets:
        assert set(bucket) == {"bucket_start_h", "bucket_end_h", "n", "bias_mw", "mae_mw", "rmse_mw"}
    # every lead < 48 lands in a closed bucket; the final one is open-ended
    assert all(b["bucket_end_h"] is not None for b in buckets[:-1])
    assert buckets[-1]["bucket_start_h"] == 48 and buckets[-1]["bucket_end_h"] is None


def test_lead_time_bucket_hours_range_enforced():
    resp = client.get("/api/metrics/by-lead-time?bucket_hours=0")
    assert resp.status_code == 400
    assert isinstance(resp.json()["detail"], str)
    resp = client.get("/api/metrics/by-lead-time")
    assert resp.status_code == 200                              # default 6 works


# ---------------------------------------------------------------- error paths

def test_out_of_window_decision_date_400_string():
    for bad in ("2026-02-01", "2025-12-31"):
        resp = client.get(f"/api/forecast-vs-actual?decision_date={bad}")
        assert resp.status_code == 400, bad
        assert isinstance(resp.json()["detail"], str), bad


def test_malformed_cutoff_4xx_string():
    resp = client.get(f"/api/forecast-vs-actual?decision_date=2026-01-15&cutoff=9am")
    assert 400 <= resp.status_code < 500
    assert isinstance(resp.json()["detail"], str)


def test_malformed_decision_date_4xx_string():
    resp = client.get("/api/forecast-vs-actual?decision_date=2026-1-15")  # strptime would accept
    assert 400 <= resp.status_code < 500
    assert isinstance(resp.json()["detail"], str)


def test_missing_required_param_is_4xx_string_detail():
    resp = client.get("/api/forecast-vs-actual")                # no decision_date at all
    assert 400 <= resp.status_code < 500
    assert isinstance(resp.json()["detail"], str)


def test_unknown_api_path_json_404_never_frontend():
    resp = client.get("/api/nope")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"detail": "Not found"}
