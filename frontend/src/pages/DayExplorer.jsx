import { Async, EmptyState, ErrorState, Skeleton } from '../components/States.jsx';
import { CutoffField, DateField } from '../components/Fields.jsx';
import { Ledger } from '../components/Ledger.jsx';
import { ErrorChart, ForecastChart } from '../components/LazyCharts.jsx';
import { DataTable } from '../components/DataTable.jsx';
import { Versions } from '../components/Versions.jsx';
import { api, useApi } from '../lib/api.js';
import { readCutoff, useConfig } from '../lib/config.js';
import { navigate } from '../lib/router.js';
import { fmtDateOnly, fmtDayTime, fmtHours, fmtMw, fmtSignedMw, fmtTime, inRange } from '../lib/format.js';

export default function DayExplorer({ route }) {
  const config = useConfig();
  const cutoff = readCutoff(route, config);
  const { from, to } = config.decision_dates;
  const requested = route.params.get('date') ?? from;
  const valid = inRange(requested, from, to);

  const day = useApi(valid ? api.forecastVsActual(requested, cutoff) : null);
  const period = useApi(api.metrics(from, to, cutoff));

  const setDate = (date) => navigate('/day', { date, cutoff });
  const setCutoff = (value) => navigate('/day', { date: valid ? requested : from, cutoff: value });

  const heading = valid
    ? day.status === 'success'
      ? `Decision on ${fmtDateOnly(day.data.decision_date)}, delivery on ${fmtDateOnly(day.data.delivery_day)}`
      : `Decision on ${fmtDateOnly(requested)}`
    : 'Day explorer';

  const columns = [
    { key: 't', header: 'Delivery (UTC)', render: (p) => fmtTime(p.start_time) },
    { key: 'f', header: 'Forecast (MW)', numeric: true, render: (p) => fmtMw(p.forecast_mw) },
    { key: 'a', header: 'Actual (MW)', numeric: true, render: (p) => fmtMw(p.actual_mw) },
    { key: 'e', header: 'Error (MW)', numeric: true, render: (p) => fmtSignedMw(p.error_mw) },
    { key: 'p', header: 'Forecast published (UTC)', render: (p) => (p.publish_time ? fmtDayTime(p.publish_time) : '—') },
    { key: 'l', header: 'Lead (h)', numeric: true, render: (p) => fmtHours(p.lead_time_h) },
  ];

  return (
    <>
      <header className="page-head">
        <h1 className="h1">{heading}</h1>
        <p className="lede">
          Only forecasts published at or before the cutoff are used. Later versions are shown, marked as unknown at decision time.
        </p>
      </header>

      <div className="controls">
        <DateField value={valid ? requested : from} min={from} max={to} onChange={setDate} />
        <CutoffField value={cutoff} options={config.cutoff_options_utc} onChange={setCutoff} />
      </div>

      {!valid ? (
        <ErrorState title="That date is outside the available range" error={new Error(`Choose a decision date from ${fmtDateOnly(from)} to ${fmtDateOnly(to)}.`)} />
      ) : (
        <Async state={day} skeleton={<Skeleton variant="page" label="Loading this day" />} errorTitle="This day could not be loaded">
          {(d) =>
            d.matched_points === 0 ? (
              <EmptyState title="No matched intervals for this day">
                Every interval was missing a forecast or an actual at this cutoff. Choose another date or cutoff.
              </EmptyState>
            ) : (
              <>
                <section className="section" aria-labelledby="day-summary-h">
                  <h2 id="day-summary-h" className="h2">Accuracy for this delivery day</h2>
                  <Ledger metrics={d.metrics} />
                </section>

                <div className="split">
                  <div className="split__main">
                    <ForecastChart points={d.points} actualsOnly={d.actuals_only ?? []} deliveryDay={d.delivery_day} />
                    <ErrorChart points={d.points} p90={period.status === 'success' ? period.data.p90_abs_error_mw : null} />
                  </div>
                  <div className="split__side">
                    <Versions key={`${d.decision_date}-${d.cutoff_utc}`} points={d.points} cutoffUtc={d.cutoff_utc} />
                  </div>
                </div>

                <section className="section" aria-labelledby="day-table-h">
                  <h2 id="day-table-h" className="h2">Every interval</h2>
                  <DataTable caption="Forecast, actual and error for each delivery interval" columns={columns} rows={d.points} rowKey={(p) => p.start_time} />
                  <p className="note">A dash means the value was missing. It is never treated as zero.</p>
                </section>
              </>
            )
          }
        </Async>
      )}
    </>
  );
}
