"""The service must not expose mutable objects held by its day cache."""

from app import service


def test_mutating_day_result_does_not_mutate_cached_result():
    service._day_cache.cache_clear()

    first = service.day("2026-01-15", "09:00")
    first["points"].clear()
    first["metrics"]["n"] = -1

    second = service.day("2026-01-15", "09:00")

    assert second["points"]
    assert second["metrics"]["n"] >= 0
