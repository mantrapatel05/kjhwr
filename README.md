# Wind Forecast Analytics

How well did Great Britain's day-ahead wind forecasts, as they were known at
decision time, actually hold up against what the wind produced?

**Configured Vercel URL:** https://kjhwr-weld-seven.vercel.app

The current deployment serves the frontend at `/`, and `/api/health` responds
successfully.

## What it is

A GB national wind **forecast vs actual** dashboard covering the January 2026
decision window, built on Elexon data. For each decision date (2026-01-01 to
2026-01-31) the app shows the wind forecast as it existed at a decision cutoff
(default 09:00 UTC on the day before delivery), the actual generation for the
delivery day, and per-interval errors — plus pooled and daily accuracy metrics
(bias, MAE, RMSE, P90 and max absolute error) and error by forecast lead time.

Every number the API serves is computed from a frozen snapshot committed with
the repo: the app never calls Elexon at request time, so the same query always
returns the same numbers. Data sources: Elexon WINDFOR (forecast versions) and
Elexon FUELHH with `fuelType = WIND` (actuals), fetched
2026-10-30T17:34:01Z and committed under `backend/data/snapshot/`. Elexon data
is used under the BMRS Data Licence.

## Stack

- **Frontend:** React + Vite + Recharts (chart colours read CSS custom
  properties at runtime), hash routing
- **Backend:** FastAPI + uvicorn, stdlib-only metrics (no numpy), snapshot
  loaded and validated once at startup
- **Data:** snapshot-backed (no runtime network calls)
- **Deployment:** Vercel (single origin: static frontend + `/api/*` rewrites),
  Docker as the portable single-container alternative (multi-stage Dockerfile:
  node stage builds the frontend, python:3.12-slim stage serves backend + built
  static files via uvicorn, honours `PORT`)

## API contract

| Endpoint | Params | Returns |
|---|---|---|
| `GET /api/health` | — | `{"status": "ok"}` |
| `GET /api/config` | — | decision/delivery windows, default cutoff and cutoff options, timezone note, snapshot fetch time |
| `GET /api/forecast-vs-actual` | `decision_date=YYYY-MM-DD`, `cutoff=HH:MM` (optional, default `09:00`) | one decision day: `points` (selected forecast vs actual with `error_mw`, `lead_time_h`, `matched`), `actuals_only`, day `metrics` |
| `GET /api/forecast-versions` | `target_time=ISO-Z`, `cutoff=ISO-Z` | every forecast version for ONE delivery interval, split at the cutoff into `available_at_cutoff` true/false with the selected version |
| `GET /api/metrics` | `from=YYYY-MM-DD`, `to=YYYY-MM-DD`, `cutoff=HH:MM` (optional) | pooled metrics over all matched errors in the range (NOT an average of daily metrics) |
| `GET /api/metrics/daily` | `cutoff=HH:MM` (optional) | one metrics row per decision date |
| `GET /api/metrics/by-lead-time` | `bucket_hours` (optional integer 1–24, default 6) | absolute/signed error by forecast age, half-open buckets, `>= 48 h` in the open-ended last bucket |

Error convention everywhere: `error = forecast − actual` (MW); positive means
the forecast ran high (over-forecast). All times UTC (UK is on GMT in January).
Missing data is never zero-filled or interpolated; metrics use matched,
non-null pairs only.

## Verified output (raw)

Quoted directly from the deployed API:

```
curl "https://kjhwr-weld-seven.vercel.app/api/config"
{"decision_dates":{"from":"2026-01-01","to":"2026-01-31"},"delivery_dates":{"from":"2026-01-02","to":"2026-02-01"},"default_cutoff_utc":"09:00","cutoff_options_utc":["06:00","08:00","09:00","10:00","12:00"],"timezone_note":"All times UTC; UK is on GMT (UTC+0) in January.","snapshot_fetched_at":"2026-10-30T17:34:01Z"}
```

```
curl "https://kjhwr-weld-seven.vercel.app/api/metrics?from=2026-01-01&to=2026-01-31&cutoff=09:00"
{"n":744,"expected":744,"coverage_pct":100.0,"bias_mw":1745.938,"mae_mw":2022.47,"rmse_mw":2497.407,"p90_abs_error_mw":4154.4,"max_abs_error_mw":6894.0}
```

## Run locally

**Backend (serves the API and, if built, the frontend):**

```
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --port 8000
```

Set `STATIC_DIR` to the built frontend directory to serve the dashboard from
the same origin (e.g. `STATIC_DIR=../frontend/dist`).

**Frontend (dev, with API proxy):**

```
cd frontend
npm install
npm run dev
```

**Frontend production build:** `npm run build` (outputs to `frontend/dist/`).

**Docker (single container, backend + built frontend):**

```
docker compose up --build
```

Then open http://localhost:8000.

## Verify the numbers

Recompute any decision day independently of the app (plain loops, no app
imports) and compare it with the live server:

```
cd backend
python scripts/recompute_day.py 2026-01-05 09:00 --server https://kjhwr-weld-seven.vercel.app
```

The final `MATCH` compares the date/cutoff fields, counts, coverage and every
reported scalar metric. It does not compare the individual point rows.

## Tests

```
python -m venv .venv
```

Activate it, then install the development requirements and run the backend tests:

```powershell
.venv\Scripts\Activate.ps1
```

```sh
source .venv/bin/activate
```

```sh
python -m pip install -r backend/requirements-dev.txt
cd backend
python -m pytest -q
```

Frontend tests: `cd frontend`, then run `npm ci` and `npm test -- --run`.

Backend covers as-of selection leakage boundaries, matching, metrics (including
P90 interpolation), time parsing and the API contract; frontend covers the four
pages and the lib logic.

## Limitations

In this snapshot, WINDFOR is positively biased against FUELHH actuals. The
alignment checks did not explain the positive monthly bias. Elexon's dataset
descriptions do not establish that WINDFOR and FUELHH cover the same generation
basis, so this analysis cannot distinguish forecast bias from a coverage or
definition mismatch.

## More documentation

Detailed engineering decisions and interview defence notes live in
`docs/DECISIONS.md` and `docs/DEFENCE_NOTES.md`; the methodology page is also
built into the app itself.
