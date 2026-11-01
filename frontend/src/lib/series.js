import { fmtTime } from './format.js';

const HOUR = 3_600_000;
export const toMs = (iso) => Date.parse(iso);
export const dayStartMs = (ymdString) => Date.parse(`${ymdString}T00:00:00Z`);

/** X axis for one delivery day: fixed 00:00 to 24:00 UTC, a tick every `stepHours`. */
export function chartAxis(deliveryDay, stepHours = 3) {
  const start = dayStartMs(deliveryDay);
  const end = start + 24 * HOUR;
  const ticks = [];
  for (let t = start; t < end; t += stepHours * HOUR) ticks.push(t);
  return { domain: [start, end], ticks };
}

function minStep(times) {
  let best = 0;
  for (let i = 1; i < times.length; i += 1) {
    const d = times[i] - times[i - 1];
    if (d > 0 && (best === 0 || d < best)) best = d;
  }
  return best;
}

/**
 * Merge forecast points and actual-only points into one row per timestamp.
 * Missing values stay null (never 0). Forecast runs are split into segments
 * (f0, f1, ...) so a missing forecast interval shows as a visible gap while the
 * line still joins consecutive forecast points across half-hour actual rows.
 */
export function buildChartRows(points, actualsOnly = []) {
  const byTime = new Map();
  const row = (t) => {
    if (!byTime.has(t)) byTime.set(t, { t, actual: null, forecast: null });
    return byTime.get(t);
  };

  for (const p of points) {
    const r = row(toMs(p.start_time));
    r.actual = p.actual_mw ?? null;
    r.forecast = p.forecast_mw ?? null;
  }
  for (const a of actualsOnly) {
    row(toMs(a.start_time)).actual = a.actual_mw ?? null;
  }

  const forecastPoints = points
    .map((p) => ({ t: toMs(p.start_time), v: p.forecast_mw ?? null }))
    .sort((a, b) => a.t - b.t);
  const step = minStep(forecastPoints.map((p) => p.t));

  let segment = -1;
  let prevT = null;
  for (const p of forecastPoints) {
    if (p.v === null) {
      prevT = null;
    } else {
      if (prevT === null || (step > 0 && p.t - prevT > 1.5 * step)) segment += 1;
      byTime.get(p.t)[`f${segment}`] = p.v;
      prevT = p.t;
    }
  }

  return {
    rows: [...byTime.values()].sort((a, b) => a.t - b.t),
    segmentKeys: Array.from({ length: segment + 1 }, (_, i) => `f${i}`),
  };
}

export function buildErrorRows(points) {
  return [...points]
    .sort((a, b) => toMs(a.start_time) - toMs(b.start_time))
    .map((p) => ({ t: toMs(p.start_time), label: fmtTime(p.start_time), error: p.error_mw ?? null }));
}
