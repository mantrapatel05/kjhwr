# -*- coding: utf-8 -*-
"""FastAPI application entrypoint (file 05).

Layering: routes.py (thin HTTP) -> service.py (orchestration, caching) ->
processing.py / metrics.py (pure logic) -> data_store.py (only snapshot reader).
"""

from fastapi import FastAPI

from .routes import router

app = FastAPI(title="Wind Forecast Analytics", version="0.1.0")
app.include_router(router)
