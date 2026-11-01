import { fmtMw, fmtPct, fmtSignedMw, biasWord } from '../lib/format.js';

function Row({ label, note, children }) {
  return (
    <div className="ledger__row">
      <dt className="ledger__term">{label}</dt>
      <dd className="ledger__value">{children}</dd>
      <dd className="ledger__note">{note}</dd>
    </div>
  );
}

/** One hero metric (MAE) plus the supporting numbers as a ledger, not equal tiles. */
export function Ledger({ metrics: m, children }) {
  const incomplete = typeof m.coverage_pct === 'number' && m.coverage_pct < 100;
  return (
    <div className="ledger">
      <div className="ledger__hero">
        <p className="ledger__label">Mean absolute error</p>
        <p className="ledger__figure">
          <span className="num ledger__number">{fmtMw(m.mae_mw)}</span>
          <span className="unit">MW</span>
        </p>
        <p className="note">Typical size of the miss, whether the forecast was too high or too low.</p>
        {children}
      </div>
      <dl className="ledger__list">
        <Row label="P90 absolute error" note="90% of matched intervals missed by this much or less.">
          <span className="num">{fmtMw(m.p90_abs_error_mw)}</span> <span className="unit">MW</span>
        </Row>
        <Row label="Bias" note={`Average of forecast minus actual: ${biasWord(m.bias_mw)}.`}>
          <span className="num">{fmtSignedMw(m.bias_mw)}</span> <span className="unit">MW</span>
        </Row>
        <Row label="RMSE" note="Like MAE, but large misses count for more.">
          <span className="num">{fmtMw(m.rmse_mw)}</span> <span className="unit">MW</span>
        </Row>
        <Row label="Largest miss" note="Worst single interval.">
          <span className="num">{fmtMw(m.max_abs_error_mw)}</span> <span className="unit">MW</span>
        </Row>
        <Row
          label="Coverage"
          note={incomplete ? 'Intervals missing a forecast or an actual are excluded, not counted as zero.' : 'Every expected interval has both a forecast and an actual.'}
        >
          <span className={`num${incomplete ? ' is-warning' : ''}`}>{fmtPct(m.coverage_pct)}</span>{' '}
          <span className="unit">{m.n} of {m.expected}</span>
        </Row>
      </dl>
    </div>
  );
}
