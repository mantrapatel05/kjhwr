# -*- coding: utf-8 -*-
"""Constants: window dates, default cutoff. All times UTC (UK = GMT in January)."""

WINDOW_DECISION_DATES = {"from": "2026-01-01", "to": "2026-01-31"}
WINDOW_DELIVERY_DATES = {"from": "2026-01-02", "to": "2026-02-01"}

# 09:00 UTC is the assumed day-ahead cutoff [DECISION, file 01 §6] — user-selectable in UI.
DEFAULT_CUTOFF_UTC = "09:00"
CUTOFF_OPTIONS_UTC = ["06:00", "08:00", "09:00", "10:00", "12:00"]
