import { useConfig } from '../lib/config.js';
import { fmtDateOnly } from '../lib/format.js';

export default function Method() {
  const config = useConfig();
  const { from, to } = config.decision_dates;
  return (
    <>
      <header className="page-head">
        <h1 className="h1">How the numbers are produced</h1>
        <p className="lede">Plain definitions, so every figure on the other pages can be checked.</p>
      </header>
      <div className="prose">
        <h2 className="h2">Decision time</h2>
        <p>
          A decision is made at the chosen cutoff (default {config.default_cutoff_utc} UTC) on the day before delivery,
          for the next day&apos;s wind generation. Decisions run from {fmtDateOnly(from)} to {fmtDateOnly(to)}.
          The cutoff is a modelling assumption rather than a market rule, so it can be changed on the Overview and Day pages.
        </p>

        <h2 className="h2">Which forecast is used</h2>
        <p>
          For each delivery interval the app uses the forecast with the latest publication time that is at or before the cutoff.
          Forecasts published later are never used for that decision. They appear in the versions list, below the cutoff rule, for context only.
        </p>

        <h2 className="h2">Matching with actual generation</h2>
        <p>
          Each selected forecast is compared with metered wind generation for the same interval start time.
          An interval missing either value is excluded from the metrics and is never treated as zero.
          Coverage reports how many expected intervals were matched.
        </p>

        <h2 className="h2">Error and sign</h2>
        <p>Error is forecast minus actual, in megawatts (MW). A positive error means the forecast was too high.</p>

        <h2 className="h2">Metrics</h2>
        <dl className="definitions">
          <div><dt>MAE</dt><dd>Mean of the absolute errors. The typical size of a miss.</dd></div>
          <div><dt>RMSE</dt><dd>Square root of the mean squared error. Like MAE, but large misses count for more.</dd></div>
          <div><dt>Bias</dt><dd>Mean of the signed errors. Positive means forecasts ran high on average. It can hide large misses that cancel out, so read it beside MAE.</dd></div>
          <div><dt>P90 absolute error</dt><dd>The value that 90% of absolute errors do not exceed, using linear interpolation between ranked errors.</dd></div>
          <div><dt>Largest miss</dt><dd>The biggest absolute error in the selection.</dd></div>
          <div><dt>Coverage</dt><dd>Matched intervals divided by expected intervals.</dd></div>
        </dl>

        <h2 className="h2">Time and data</h2>
        <p>{config.timezone_note} Actuals are Elexon FUELHH wind generation; forecasts are Elexon WINDFOR.</p>
      </div>
    </>
  );
}
