# -*- coding: utf-8 -*-
"""Vercel entrypoint for the FastAPI backend (serverless).

Skeleton for Day-1 deploy verification: /api/health -> {"status": "ok"}.
Tomorrow (file 05) the real app — config, as-of selection, metrics — mounts here so the
single FastAPI app serves both the function and the React build from one origin.
"""

from fastapi import FastAPI

api = FastAPI(title="Wind Forecast Analytics", version="0.1.0")


@api.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
