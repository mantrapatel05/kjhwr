import { Async, EmptyState, Skeleton } from '../components/States.jsx';
import { LeadChart } from '../components/LazyCharts.jsx';
import { DataTable } from '../components/DataTable.jsx';
import { api, useApi } from '../lib/api.js';
import { fmtMw, fmtSignedMw, leadLabel } from '../lib/format.js';

export default function LeadTime() {
  const state = useApi(api.byLeadTime(6));

  const columns = [
    { key: 'l', header: 'Lead time', render: (b) => b.label },
    { key: 'mae', header: 'MAE (MW)', numeric: true, render: (b) => fmtMw(b.mae_mw) },
    { key: 'rmse', header: 'RMSE (MW)', numeric: true, render: (b) => fmtMw(b.rmse_mw) },
    { key: 'bias', header: 'Bias (MW)', numeric: true, render: (b) => fmtSignedMw(b.bias_mw) },
    { key: 'n', header: 'Matched pairs', numeric: true, render: (b) => b.n },
  ];

  return (
    <>
      <header className="page-head">
        <h1 className="h1">How does accuracy change with forecast age?</h1>
        <p className="lede">
          Lead time is the gap between a forecast being published and the interval it covers.
          This view uses every published version, not only the one known at a decision cutoff.
        </p>
      </header>
      <section className="section" aria-labelledby="lead-h">
        <h2 id="lead-h" className="h2">Error by lead time</h2>
        <Async state={state} skeleton={<Skeleton variant="chart" label="Loading lead-time results" />} errorTitle="Lead-time results could not be loaded">
          {(raw) => {
            const buckets = raw.map((b) => ({ ...b, label: leadLabel(b) }));
            if (!buckets.length) {
              return <EmptyState title="No lead-time results">No forecast versions could be matched with actuals.</EmptyState>;
            }
            return (
              <>
                <LeadChart buckets={buckets} />
                <DataTable caption="Forecast error by lead time" columns={columns} rows={buckets} rowKey={(b) => b.label} />
              </>
            );
          }}
        </Async>
      </section>
    </>
  );
}
