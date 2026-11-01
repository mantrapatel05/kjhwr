# -*- coding: utf-8 -*-
"""FastAPI application entrypoint (file 05).

Layering: routes.py (thin HTTP) -> service.py (orchestration, caching) ->
processing.py / metrics.py (pure logic) -> data_store.py (only snapshot reader).

Startup: the snapshot is loaded and validated ONCE at import (fail fast before
the server accepts traffic). If the built frontend exists (env STATIC_DIR,
default ./static) it is mounted LAST at "/" — hash routing needs no SPA fallback,
and unknown /api/* paths are answered by the router's JSON catch-all first.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import service
from .routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Wind Forecast Analytics", version="0.1.0")

# CORS for local dev only (frontend on 5173); production is same-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    logger.info(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000.0,
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """Malformed params must return a STRING detail, never FastAPI's default list."""
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", []))
    return JSONResponse(
        status_code=422,
        content={"detail": f"invalid request: {first.get('msg', 'validation failed')} ({location})"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log with traceback, never leak internals; a human-readable constant instead."""
    logger.exception("unhandled error serving %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal error"})


# /api routes (thin) — before anything else is mounted.
app.include_router(router)

# Snapshot ONCE at startup: missing or malformed files stop the process here.
service.load()

# Built frontend LAST, only if the directory exists (deployments decide via env).
_static_dir = Path(os.environ.get("STATIC_DIR", "./static"))
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
