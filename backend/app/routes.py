# -*- coding: utf-8 -*-
"""HTTP layer (file 05 §2). THIN by design: declare endpoints, call service, return.

No business logic here — selection/matching (processing) and orchestration
(service) hold the rules, and their tests pin them.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
