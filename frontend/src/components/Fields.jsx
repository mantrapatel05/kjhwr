import { useId } from 'react';
import { addDays, fmtDayMonthOnly, fmtDateOnly } from '../lib/format.js';

export function CutoffField({ value, options, onChange }) {
  const id = useId();
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>Decision cutoff (UTC)</label>
      <select id={id} className="control" value={value} onChange={(e) => onChange(e.target.value)} aria-describedby={`${id}-help`}>
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
      <p id={`${id}-help`} className="field__help">On the day before delivery</p>
    </div>
  );
}

export function DateField({ value, min, max, onChange }) {
  const id = useId();
  const prev = addDays(value, -1);
  const next = addDays(value, 1);
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>Decision date</label>
      <div className="field__row">
        <button type="button" className="button" aria-label="Previous decision date" disabled={prev < min} onClick={() => onChange(prev)}>
          Prev
        </button>
        <input id={id} className="control" type="date" value={value} min={min} max={max} onChange={(e) => e.target.value && onChange(e.target.value)} aria-describedby={`${id}-help`} />
        <button type="button" className="button" aria-label="Next decision date" disabled={next > max} onClick={() => onChange(next)}>
          Next
        </button>
      </div>
      <p id={`${id}-help`} className="field__help">Available {fmtDayMonthOnly(min)} to {fmtDateOnly(max)}</p>
    </div>
  );
}
