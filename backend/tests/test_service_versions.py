from datetime import datetime, timezone

from app import service


def test_versions_selects_last_row_when_publish_times_tie(monkeypatch):
    target = datetime(2026, 1, 16, 10, tzinfo=timezone.utc)
    publish_time = "2026-01-15T07:30:00Z"
    monkeypatch.setattr(service, "_FORECASTS", [])
    monkeypatch.setattr(
        service,
        "_FORECASTS_BY_START",
        {
            target: [
                {"publish_time": publish_time, "generation": 5100.0},
                {"publish_time": publish_time, "generation": 5200.0},
            ]
        },
    )

    result = service.versions(
        target,
        datetime(2026, 1, 15, 9, tzinfo=timezone.utc),
    )

    entries = result["versions"]
    assert [entry["forecast_mw"] for entry in entries] == [5100.0, 5200.0]
    assert [entry["selected"] for entry in entries] == [False, True]
