import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import App from './App.jsx';
import { clearApiCache } from './lib/api.js';

// Fixtures follow the endpoint shapes in 05_ARCHITECTURE_AND_API.md.
// The numbers are invented for tests only.
const config = {
  decision_dates: { from: '2026-01-01', to: '2026-01-31' },
  delivery_dates: { from: '2026-01-02', to: '2026-02-01' },
  default_cutoff_utc: '09:00',
  cutoff_options_utc: ['06:00', '09:00', '12:00'],
  timezone_note: 'All times UTC; UK is on GMT (UTC+0) in January.',
  snapshot_fetched_at: '2026-10-29T10:00:00Z',
};
const metrics = { n: 4, expected: 4, coverage_pct: 100, bias_mw: 0, mae_mw: 400, rmse_mw: 509.9, p90_abs_error_mw: 740, max_abs_error_mw: 800 };
const day = {
  decision_date: '2026-01-14', cutoff_utc: '2026-01-14T09:00:00Z', delivery_day: '2026-01-15',
  expected_points: 4, matched_points: 3,
  points: [
    { start_time: '2026-01-15T10:00:00Z', forecast_mw: 5000, actual_mw: 4200, publish_time: '2026-01-14T07:30:00Z', lead_time_h: 26.5, error_mw: 800, matched: true },
    { start_time: '2026-01-15T11:00:00Z', forecast_mw: 4800, actual_mw: 5000, publish_time: '2026-01-14T07:30:00Z', lead_time_h: 27.5, error_mw: -200, matched: true },
    { start_time: '2026-01-15T12:00:00Z', forecast_mw: null, actual_mw: 3000, publish_time: null, lead_time_h: null, error_mw: null, matched: false },
  ],
  actuals_only: [{ start_time: '2026-01-15T10:30:00Z', actual_mw: 4600 }],
  metrics: { ...metrics, n: 2, expected: 3, coverage_pct: 66.7 },
};
const versions = {
  target_time: '2026-01-15T10:00:00Z', cutoff_utc: '2026-01-14T09:00:00Z',
  versions: [
    { publish_time: '2026-01-14T04:30:00Z', forecast_mw: 5500, lead_time_h: 29.5, available_at_cutoff: true, selected: false },
    { publish_time: '2026-01-14T07:30:00Z', forecast_mw: 5000, lead_time_h: 26.5, available_at_cutoff: true, selected: true },
    { publish_time: '2026-01-14T09:30:00Z', forecast_mw: 4800, lead_time_h: 24.5, available_at_cutoff: false, selected: false },
  ],
};
const daily = [{ decision_date: '2026-01-01', delivery_day: '2026-01-02', n: 24, bias_mw: 10, mae_mw: 300, rmse_mw: 400, p90_abs_error_mw: 700, coverage_pct: 100 }];
const lead = [{ bucket_start_h: 0, bucket_end_h: 6, n: 100, bias_mw: 1, mae_mw: 200, rmse_mw: 260 }, { bucket_start_h: 48, bucket_end_h: null, n: 50, bias_mw: -5, mae_mw: 900, rmse_mw: 1100 }];

function mockFetch(overrides = {}) {
  const routes = {
    '/api/config': config, '/api/metrics?': metrics, '/api/metrics/daily': daily,
    '/api/forecast-vs-actual': day, '/api/forecast-versions': versions, '/api/metrics/by-lead-time': lead, ...overrides,
  };
  globalThis.fetch = vi.fn(async (url) => {
    const key = Object.keys(routes).find((k) => url.includes(k));
    const body = key ? routes[key] : null;
    if (body instanceof Error) return { ok: false, status: 500, json: async () => ({ detail: body.message }) };
    return { ok: true, status: 200, json: async () => body };
  });
}

beforeEach(() => {
  clearApiCache();
  window.location.hash = '';
});

describe('App', () => {
  it('shows the overview ledger with units and the P90 sentence', async () => {
    mockFetch();
    render(<App />);
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(/day-ahead wind forecast/i);
    expect(await screen.findByText('P90 absolute error')).toBeInTheDocument();
    expect(await screen.findByText(/buffer of 740 MW would have covered 90%/)).toBeTruthy();
    expect(screen.getByText('Mean absolute error')).toBeTruthy();
  });

  it('shows a retryable error when the config cannot load', async () => {
    mockFetch({ '/api/config': new Error('boom') });
    render(<App />);
    expect(await screen.findByRole('alert')).toHaveTextContent('boom');
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
  });

  it('day explorer: missing values show a dash, versions split at the cutoff', async () => {
    mockFetch();
    window.location.hash = '#/day?date=2026-01-14&cutoff=09:00';
    render(<App />);
    expect(await screen.findByRole('heading', {
      level: 1,
      name: 'Decision on 14 Jan 2026, delivery on 15 Jan 2026',
    })).toBeTruthy();
    const table = await screen.findByRole('table', { name: /each delivery interval/i });
    const rows = within(table).getAllByRole('row');
    expect(rows).toHaveLength(4); // header + 3 points
    expect(within(rows[3]).getAllByText('—').length).toBeGreaterThanOrEqual(3);
    expect(await screen.findByText(/Decision cutoff, 14 Jan 09:00 UTC/)).toBeTruthy();
    expect(screen.getByText(/Used for this decision/)).toBeTruthy();
    expect(screen.getByText(/Published after the cutoff/)).toBeTruthy();
    expect(screen.getByText(/66\.7%/)).toBeTruthy();
  });

  it('day explorer: rejects a date outside the window without calling the API for it', async () => {
    mockFetch();
    window.location.hash = '#/day?date=2026-03-01';
    render(<App />);
    expect(await screen.findByText('That date is outside the available range')).toBeTruthy();
    const calls = globalThis.fetch.mock.calls.map((c) => c[0]);
    expect(calls.some((u) => u.includes('forecast-vs-actual'))).toBe(false);
  });

  it('day explorer: surfaces a server error message', async () => {
    mockFetch({ '/api/forecast-vs-actual': new Error('Decision date outside January 2026') });
    window.location.hash = '#/day?date=2026-01-14';
    render(<App />);
    expect(await screen.findByText('Decision date outside January 2026')).toBeTruthy();
  });

  it('lead time page labels open-ended buckets', async () => {
    mockFetch();
    window.location.hash = '#/lead-time';
    render(<App />);
    await waitFor(() => expect(screen.getByRole('table', { name: /by lead time/i })).toBeTruthy());
    expect(screen.getByText('48+ h')).toBeTruthy();
  });

  it('marks the current page in the nav', async () => {
    mockFetch();
    window.location.hash = '#/method';
    render(<App />);
    const nav = await screen.findByRole('navigation', { name: 'Primary' });
    expect(within(nav).getByRole('link', { name: 'Method' })).toHaveAttribute('aria-current', 'page');
  });
});
