from fastapi import FastAPI

app = FastAPI(title="Wind Forecast Analytics", version="0.1.0")
# Keep the alias for local imports; Vercel detects ``app``.
api = app


@api.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
