import { useId, useState } from 'react';
import { api, useApi } from '../lib/api.js';
import { fmtDayTime, fmtHours, fmtMw, fmtTime } from '../lib/format.js';
import { Async, EmptyState, Skeleton } from './States.jsx';

function statusOf(v) {
  if (v.selected) return 'Used for this decision';
  if (v.available_at_cutoff) return 'Superseded by a later version';
  return 'Published after the cutoff, not known at decision time';
}

function VersionList({ data }) {
  if (!data.versions.length) {
    return <EmptyState title="No versions found">No forecast was published for this interval.</EmptyState>;
  }
  const sorted = [...data.versions].sort((a, b) => Date.parse(a.publish_time) - Date.parse(b.publish_time));
  const firstLate = sorted.findIndex((v) => !v.available_at_cutoff);
  const split = firstLate === -1 ? sorted.length : firstLate;
  const known = sorted.slice(0, split);
  const later = sorted.slice(split);

  const item = (v) => (
    <li key={v.publish_time} className="version" data-state={v.selected ? 'selected' : v.available_at_cutoff ? 'known' : 'later'}>
      <span className="version__time">{fmtDayTime(v.publish_time)} UTC</span>
      <span className="version__mw num">{fmtMw(v.forecast_mw)} MW</span>
      <span className="version__status">
        <span className="num">{fmtHours(v.lead_time_h)} h ahead</span> · {statusOf(v)}
      </span>
    </li>
  );

  return (
    <ol className="versions">
      {known.map(item)}
      <li className="cutoff-rule">Decision cutoff, {fmtDayTime(data.cutoff_utc)} UTC</li>
      {later.map(item)}
    </ol>
  );
}

/** Requirement 1: every version published for one interval, split at the cutoff. */
export function Versions({ points, cutoffUtc }) {
  const id = useId();
  const [target, setTarget] = useState(points[0]?.start_time ?? '');
  const state = useApi(target ? api.versions(target, cutoffUtc) : null);

  return (
    <section className="panel" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`} className="h2">Forecast versions for one interval</h2>
      <p className="note">Versions published after the cutoff are shown below the rule. They were not known when the decision was made.</p>
      <div className="field">
        <label className="field__label" htmlFor={`${id}-t`}>Delivery interval (UTC)</label>
        <select id={`${id}-t`} className="control" value={target} onChange={(e) => setTarget(e.target.value)}>
          {points.map((p) => (
            <option key={p.start_time} value={p.start_time}>{fmtTime(p.start_time)}</option>
          ))}
        </select>
      </div>
      <Async state={state} skeleton={<Skeleton variant="list" label="Loading forecast versions" />} errorTitle="Forecast versions could not be loaded">
        {(data) => <VersionList data={data} />}
      </Async>
    </section>
  );
}
