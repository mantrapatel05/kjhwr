import { Async, EmptyState, Skeleton } from '../components/States.jsx';
import { CutoffField } from '../components/Fields.jsx';
import { Ledger } from '../components/Ledger.jsx';
import { DailyChart } from '../components/LazyCharts.jsx';
import { DataTable } from '../components/DataTable.jsx';
import { api, useApi } from '../lib/api.js';
import { readCutoff, useConfig } from '../lib/config.js';
import { buildHash, navigate } from '../lib/router.js';
import { fmtDateOnly, fmtDayMonthOnly, fmtMw, fmtPct, fmtSignedMw } from '../lib/format.js';

export default function Overview({ route }) {
  const config = useConfig();
  const cutoff = readCutoff(route, config);
  const { from, to } = config.decision_dates;
  const metrics = useApi(api.metrics(from, to, cutoff));
  const daily = useApi(api.daily(cutoff));

  const openDay = (date) => navigate('/day', { date, cutoff });
  const setCutoff = (value) => navigate('/', { cutoff: value });

  const columns = [
    { key: 'd', header: 'Decision date', render: (r) => <a href={buildHash('/day', { date: r.decision_date, cutoff })}>{fmtDayMonthOnly(r.decision_date)}</a> },
    { key: 'mae', header: 'MAE (MW)', numeric: true, render: (r) => fmtMw(r.mae_mw) },
    { key: 'bias', header: 'Bias (MW)', numeric: true, render: (r) => fmtSignedMw(r.bias_mw) },
    { key: 'p90', header: 'P90 (MW)', numeric: true, render: (r) => fmtMw(r.p90_abs_error_mw) },
    { key: 'n', header: 'Matched', numeric: true, render: (r) => r.n },
    { key: 'cov', header: 'Coverage', numeric: true, render: (r) => fmtPct(r.coverage_pct) },
  ];

  return (
    <>
      <header className="page-head">
        <h1 className="h1">How wrong can the day-ahead wind forecast be?</h1>
        <p className="lede">
          Forecasts as known at {cutoff} UTC on the day before delivery, compared with metered wind
          generation. Decisions made {fmtDayMonthOnly(from)} to {fmtDateOnly(to)}.
        </p>
      </header>

      <div className="controls">
        <CutoffField value={cutoff} options={config.cutoff_options_utc} onChange={setCutoff} />
      </div>

      <section className="section" aria-labelledby="summary-h">
        <h2 id="summary-h" className="h2">Forecast error over the period</h2>
        <Async state={metrics} skeleton={<Skeleton variant="ledger" label="Loading accuracy summary" />} errorTitle="The accuracy summary could not be loaded">
          {(m) =>
            m.n === 0 ? (
              <EmptyState title="No matched data for this cutoff">
                Every interval was missing a forecast or an actual. Try a different cutoff.
              </EmptyState>
            ) : (
              <Ledger metrics={m}>
                <p className="planning">
                  At a {cutoff} UTC cutoff, a buffer of {fmtMw(m.p90_abs_error_mw)} MW would have covered 90% of matched intervals.
                </p>
              </Ledger>
            )
          }
        </Async>
      </section>

      <section className="section" aria-labelledby="daily-h">
        <h2 id="daily-h" className="h2">Error by day</h2>
        <Async state={daily} skeleton={<Skeleton variant="chart" label="Loading daily results" />} errorTitle="Daily results could not be loaded">
          {(days) => (
            <>
              <DailyChart days={days} periodMae={metrics.status === 'success' ? metrics.data.mae_mw : null} onSelect={openDay} />
              <p className="note">Select a bar to open that decision date.</p>
              <details className="details">
                <summary>Daily results as a table</summary>
                <DataTable caption="Forecast error by decision date" columns={columns} rows={days} rowKey={(r) => r.decision_date} />
              </details>
            </>
          )}
        </Async>
      </section>
    </>
  );
}
