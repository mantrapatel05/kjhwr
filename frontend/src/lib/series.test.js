import { describe, expect, it } from 'vitest';
import { buildChartRows, buildErrorRows, chartAxis } from './series.js';
import { addDays, fmtSignedMw, fmtMw, fmtTime, inRange, leadLabel } from './format.js';
import { buildHash, parseHash } from './router.js';

const pt = (time, f, a) => ({ start_time: `2026-01-15T${time}:00Z`, forecast_mw: f, actual_mw: a, error_mw: f === null || a === null ? null : f - a });

describe('chartAxis', () => {
  it('spans one UTC day with a tick every 3 hours', () => {
    const { domain, ticks } = chartAxis('2026-01-15');
    expect(domain[1] - domain[0]).toBe(24 * 3_600_000);
    expect(ticks).toHaveLength(8);
    expect(ticks[0]).toBe(Date.parse('2026-01-15T00:00:00Z'));
  });
});

describe('buildChartRows', () => {
  it('merges half-hour actuals without inventing forecasts', () => {
    const { rows } = buildChartRows([pt('10:00', 5000, 4800), pt('11:00', 5100, 5200)], [{ start_time: '2026-01-15T10:30:00Z', actual_mw: 4900 }]);
    expect(rows.map((r) => r.t)).toEqual([
      Date.parse('2026-01-15T10:00:00Z'), Date.parse('2026-01-15T10:30:00Z'), Date.parse('2026-01-15T11:00:00Z'),
    ]);
    expect(rows[1].forecast).toBeNull();
    expect(rows[1].actual).toBe(4900);
  });

  it('keeps one segment across half-hour rows', () => {
    const { segmentKeys } = buildChartRows([pt('10:00', 1, 1), pt('11:00', 2, 2)], [{ start_time: '2026-01-15T10:30:00Z', actual_mw: 1 }]);
    expect(segmentKeys).toEqual(['f0']);
  });

  it('splits segments at a missing forecast and never turns it into zero', () => {
    const { rows, segmentKeys } = buildChartRows([pt('10:00', 1, 1), pt('11:00', null, 2), pt('12:00', 3, 3)]);
    expect(segmentKeys).toEqual(['f0', 'f1']);
    expect(rows[1].forecast).toBeNull();
    expect(rows[1].f0).toBeUndefined();
    expect(rows[1].f1).toBeUndefined();
  });

  it('keeps a zero actual as zero', () => {
    const { rows } = buildChartRows([pt('10:00', 10, 0)]);
    expect(rows[0].actual).toBe(0);
  });
});

describe('buildErrorRows', () => {
  it('keeps missing errors null', () => {
    const rows = buildErrorRows([pt('10:00', 5, null), pt('09:00', 5, 4)]);
    expect(rows.map((r) => r.label)).toEqual(['09:00', '10:00']);
    expect(rows[0].error).toBe(1);
    expect(rows[1].error).toBeNull();
  });
});

describe('format', () => {
  it('formats signed MW with a true minus and no negative zero', () => {
    expect(fmtSignedMw(800)).toBe('+800');
    expect(fmtSignedMw(-200)).toBe('−200');
    expect(fmtSignedMw(0.4)).toBe('0');
    expect(fmtSignedMw(null)).toBe('—');
  });
  it('shows missing values as a dash, zero as 0', () => {
    expect(fmtMw(null)).toBe('—');
    expect(fmtMw(0)).toBe('0');
    expect(fmtMw(5200)).toBe('5,200');
  });
  it('formats times in UTC with 24h clock', () => {
    expect(fmtTime('2026-01-15T00:00:00Z')).toBe('00:00');
    expect(fmtTime('2026-01-15T09:30:00Z')).toBe('09:30');
  });
  it('handles dates', () => {
    expect(addDays('2026-01-31', 1)).toBe('2026-02-01');
    expect(inRange('2026-01-15', '2026-01-01', '2026-01-31')).toBe(true);
    expect(inRange('2026-02-01', '2026-01-01', '2026-01-31')).toBe(false);
    expect(inRange('nonsense', '2026-01-01', '2026-01-31')).toBe(false);
  });
  it('labels lead-time buckets', () => {
    expect(leadLabel({ bucket_start_h: 0, bucket_end_h: 6 })).toBe('0–6 h');
    expect(leadLabel({ bucket_start_h: 48, bucket_end_h: null })).toBe('48+ h');
  });
});

describe('router', () => {
  it('round-trips path and params, dropping empty values', () => {
    expect(buildHash('/day', { date: '2026-01-14', cutoff: '09:00', x: null })).toBe('#/day?date=2026-01-14&cutoff=09%3A00');
    const r = parseHash('#/day?date=2026-01-14&cutoff=09%3A00');
    expect(r.path).toBe('/day');
    expect(r.params.get('cutoff')).toBe('09:00');
    expect(parseHash('').path).toBe('/');
  });
});
