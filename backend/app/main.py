from fastapi import FastAPI

app = FastAPI(title="Wind Forecast Analytics", version="0.1.0")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
