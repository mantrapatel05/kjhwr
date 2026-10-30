# -*- coding: utf-8 -*-
"""Skeleton FastAPI app — proves hosting works end to end (Day 1 goal, file 11).

Endpoints added tomorrow (file 05): /api/config, /api/forecast-vs-actual,
/api/forecast-versions, /api/metrics, /api/metrics/daily, /api/metrics/by-lead-time.
"""

from fastapi import FastAPI

app = FastAPI(title="Wind Forecast Analytics", version="0.1.0")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
