# DEFENCE NOTES — 12 Q&A

> Numbers below come from verified runs only (inspection report, pytest runs,
> STOP GATE 4 raw output and the recompute script). No invented numbers.

## Q1. Why a frozen snapshot instead of calling Elexon live?

Determinism and leakage-safety. The decision problem is about what was KNOWN at
a cutoff; serving live data at request time could show data that wasn't public
yet and would make every session produce different numbers. The snapshot was
fetched 2026-10-30T17:34:01Z, committed, and validated once at startup. The app
never performs network calls at runtime. Elexon data is attributed per the BMRS
Data Licence.

## Q2. Where could leakage sneak into this system, and what stops it?

The classic leak: selecting a forecast version published AFTER the decision
cutoff. It is stopped in exactly one place — `processing.select_as_of` keeps
only versions with publishTime <= cutoff (inclusive) — and asserted twice:
in unit tests and at the HTTP layer (every non-null publish_time in an
/api/forecast-vs-actual response must be <= cutoff_utc). The snapshot itself
also over-fetches into December 2025 publishes, which makes the boundary a real,
tested behaviour rather than a favourable accident of the data.

## Q3. How does the app handle missing or half-hourly data?

Missing stays missing: no zeros, no interpolation. Points with a null forecast or null actual stay unmatched (error stays null), and actuals that never got an
eligible forecast (the :30 half-hours of FUELHH against the hourly WINDFOR
grid) are displayed separately in `actuals_only`. Coverage denominators come
from the product's hourly grid, not from the matched set, so an optimistic
coverage number is impossible.

## Q4. Why is metric pooling not an average of daily metrics?

An average of daily MAEs weights each DAY equally regardless of how many good
intervals it has. `/api/metrics` pools every matched individual error in the
range and computes once. The contract test asserts pooled n equals the sum of
per-day n over /api/metrics/daily.

## Q5. How is P90 computed without numpy?

Sorted absolute errors, position = 0.9 * (n − 1), linear interpolation between
the neighbouring ranks — identical to numpy.percentile's default "linear"
method. A hand-checkable case in the metrics tests pins the value. numpy was
skipped to keep the image small; the metric semantics were not.

## Q6. What does a positive error mean?

error = forecast − actual (MW): positive means the forecast ran HIGH
(over-forecast). The sign convention is stated in the README and visible on the
charts (over-forecast vs under-forecast split), so the reader never has to
guess. Bias is the mean signed error.

## Q7. Why no MAPE?

Actual GB wind is frequently near zero; percentage error explodes exactly when
the product matters most (calm, decision-critical days). Absolute MW metrics
plus the over/under split answer the same question honestly.

## Q8. What is the timezone story?

UTC everywhere. January is GMT, so UTC equals UK local time — no conversion is
ever applied, and /api/config states this in its `timezone_note`. Naive
timestamps and non-padded dates are rejected; nothing is silently assumed.

## Q9. Walk me through the API design. What's a "day payload"?

Six endpoints: config (the app's own constants), forecast-vs-actual (one
decision day: points, actuals_only, metrics), forecast-versions (knowledge
timeline for ONE interval, split at the cutoff — available_at_cutoff false after
it, exactly one selected even if its forecast is null), metrics (pooled),
metrics/daily (one row per decision date), metrics/by-lead-time (error by
forecast age, half-open buckets with an open-ended last bucket >= 48 h).

## Q10. How would a recompute script verify the server's numbers?

`backend/scripts/recompute_day.py` recomputes one decision day INDEPENDENTLY of the
app — plain loops, stdlib only, no app imports — rebuilding the as-of
selection, matching and metrics straight from the snapshot, then (with
`--server`) fetching the server's own /api/forecast-vs-actual payload and
printing the two answers side by side. Run against the deployed app:

```
cd backend
python scripts/recompute_day.py 2026-01-05 09:00 --server https://kjhwr-weld-seven.vercel.app
```

Both answers, per metric:

| metric              | recompute (snapshot) | server (/api/forecast-vs-actual) |
|---------------------|----------------------|----------------------------------|
| matched / expected  | 24 / 24              | 24 / 24                          |
| bias_mw             | 1938.083             | 1938.083                         |
| mae_mw              | 2158.250             | 2158.250                         |
| rmse_mw             | 2531.174             | 2531.174                         |
| p90_abs_error_mw    | 3791.000             | 3791.000                         |
| max_abs_error_mw    | 4291.000             | 4291.000                         |

The script's raw output ends with the verdict:

```
MATCH: recompute agrees with the server
```

Twenty-four of twenty-four points matched and identical metrics on every row:
the selection and metric paths are verified end-to-end without trusting the
same code twice — the script is a genuinely independent second opinion, and it
exits non-zero if the two ever disagree.

## Q11. How does the deployment work?

Single origin: Vercel serves the built frontend (Vite static) and routes /api/*
to the FastAPI service. CORS stays dev-only. CORS-vs-Vercel caveat: the browser
trips across the same origin, so no cross-origin rules are needed in production.
Docker is built and locally tested as the portable single-container alternative:
a multi-stage Dockerfile at the repo root builds the frontend in a node stage,
and the python:3.12-slim stage serves the backend plus the built static files
with uvicorn; PORT is honoured; docker-compose.yml wraps it in one command; a
.dockerignore keeps raw chunk data out of the image (the snapshot only — never
data/raw — ships in the image).

## Q12. What are the honest limitations?

- One country, one month, one fuel: no regional split, no other renewables
- The snapshot is frozen (published data can be revised; ours is point-in-time)
- WINDFOR's hourly product vs FUELHH's half-hourly actuals means half the
  actual rows can never have an as-of forecast — shown as such, not hidden
- Lead-time buckets are binned; within-bucket structure doesn't exist in this
  view
- No user auth or persistence — a read-only analytics dashboard by design
