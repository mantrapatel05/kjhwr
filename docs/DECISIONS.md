# DECISIONS

> Every number in this document comes from verified runs only (the inspection
> report, pytest runs, the STOP GATE 4 raw output and the recompute script).
> No invented numbers.

## D1 — GB national wind only

The product compares the country-level GB wind forecast with GB wind actuals.
Elexon's FUELHH provides actual generation per fuel type (Puzzle-like split);
we take the WIND rows only. Regional/zone breakdowns are out of scope.
Consequence: one series in, one forecast product (WINDFOR) — the analysis is a
product-vs-product study, not a farm-level study.

## D2 — Snapshot, not live API

The app serves a frozen snapshot of the Elexon Insights API, fetched
**2026-10-30T17:34:01Z** and committed with the repo (`backend/data/snapshot/`).
The deployed app never calls Elexon at request time.

Why: deterministic numbers (every future session computes identical output);
zero risk of new data leaking past a cutoff; the review panel sees the same
dataset the README documents; no runtime network dependency (Vercel serverless
friendly). Elexon data is used under the BMRS Data Licence, attributed in the
README and the app footer.

## D3 — As-of selection: latest version at or before the cutoff, inclusive

For each delivery interval, the eligible forecast version is the one with the
greatest publishTime **<= cutoff** (inclusive). A version published after the
cutoff may never influence anything downstream — the leakage rule, enforced in
`processing.select_as_of` and re-tested at the HTTP layer
(every non-null publish_time in a response is <= cutoff_utc).

Duplicate `(startTime, publishTime)` rows: first occurrence kept; a later
duplicate with a DIFFERENT generation replaces it with a logged warning
(last-of-file wins). Inspection found zero duplicate conflicts in the snapshot.

## D4 — No fallback to older versions

If the latest eligible version for an interval has a null forecast, the point
stays unmatched with a null forecast — the code never falls back to an older
non-null version. Anaemic honesty beats a quietly better number.
Real-data note: the January snapshot contains zero null WINDFOR values, so this
rule is exercised by tests (null-forecast fixture), not by production data.

## D5 — Missing stays missing

Missing forecasts never become 0 and are never interpolated:
- unmatched points stay in the response with null forecast/error, `matched: false`
- actuals whose timestamps are absent from every WINDFOR version (e.g. FUELHH
  half-hours at :30) are shown separately in `actuals_only`
- an expected timestamp with no forecast available by the cutoff has no `points`
  row; its actual is not in `actuals_only`, but the timestamp remains in the
  coverage denominator
- metrics use matched, non-null pairs only; a day with no matches yields
  n = 0 and null metrics, never NaN

## D6 — UTC everywhere

January is GMT, so UTC equals UK local time and no conversion is ever applied.
Naive timestamps (no offset) are rejected by `timeutil.parse_utc` — assuming UTC
would hide upstream bugs. Decision dates must be strict `YYYY-MM-DD` (the padded
shape; `2026-1-15` is rejected). The cutoff is always an explicit, visible
parameter.

## D7 — Expected points = timestamps present in any forecast version

`expected_points` counts distinct forecast startTimes in the delivery window
across ALL WINDFOR versions, including versions published after the cutoff.
Coverage = matched / expected. A timestamp with only future-published versions
counts in the denominator. An empty set of forecast timestamps has expected 0;
there is no synthetic hourly-grid fallback.

## D8 — Metrics: pooled, error convention, no MAPE, 3 dp at serialisation

- error = forecast − actual (MW); positive means over-forecast
- `/api/metrics` pools ALL matched individual errors over the date range — it is
  NOT an average of daily metrics
- RMSE >= MAE holds by construction (sanity invariant pinned in tests)
- MAPE deliberately absent: actual wind can be near zero and it explodes
- rounding to 3 decimals happens only at serialisation; full precision flows
  through the math until then
- numpy is not a dependency; P90 is hand-rolled linear interpolation, matching
  numpy.percentile's default "linear" method, pinned by a hand-checkable case
  in the tests

## D9 — Lead-time scope refinements

Lead-time analysis runs over ALL versions (not one as-of series), restricted to:
publishTime in [2026-01-01, 2026-02-01), startTime in [2026-01-02, 2026-02-02),
startTime > publishTime, generation not null, and a non-null actual at the same
startTime. Buckets are half-open [start, end); everything >= 48 h lands in the
final open-ended bucket (`bucket_end_h: null`); empty buckets are returned with
null metrics.

## D10 — Dependency deviation: requests instead of httpx

The brief's scripts section mentions httpx; the fetch script uses
`requests` (2.32.5) instead — one synchronous dependency, already available,
sufficient for chunked GETs. Recorded as a deliberate deviation; nothing in the
backend at request time performs HTTP.

## D11 — Strict parsing over silent recovery

`parse_utc` rejects naive strings; `parse_decision_date` rejects non-padded
shapes via regex before strptime (strptime alone would accept `2026-1-15`).
Bad input fails loudly with a string detail in the API (422/400), never silently
normalised.

## D12 — Snapshot file naming

The fetched FUELHH snapshot is committed as `fuelhh_wind.json.gz` (WIND-only by
construction), matching the spec's file name; the fetch filter drops every
non-WIND fuelType row (verified 100% WIND in the inspection report).

## D13 — Layering and load-once

FastAPI app entrypoint → thin `routes.py` (validation + serialisation) →
`service.py` (orchestration, day cache keyed by (decision_date, cutoff),
indexes built once at load) → pure `processing.py`/`metrics.py` → `data_store.py`
(the ONLY snapshot reader). The snapshot loads and validates once during app
module import, before the server accepts requests; later /api errors are
application errors, not data-loading errors.

## D14 — Serving and deployment

Vercel is configured with an API service (FastAPI, root `backend/`) and a
frontend service (Vite, root `frontend/`), with `/api/*` rewrites to the API.
The current deployment serves the frontend at `/`; `/api/health` also returns
HTTP 200. The frontend route is verified on the live deployment.
CORS is dev-only (http://localhost:5173). In dev, the frontend proxies `/api`
to uvicorn on :8000. Docker (Stage 6) provides the portable single-container
alternative: frontend built in a node stage, served by the Python image with
uvicorn and a STATIC_DIR mount for the built files.

## D15 — Frontend design system

The dashboard uses tokens + base stylesheets following the design of an earlier
own project (paper background, ink text, teal accent, mono eyebrows, hairline
panel grid, numbered section headings, dark tooltips). Chart colours read CSS
custom properties at runtime (`src/lib/tokens.js`), so palette changes never
touch chart code.
