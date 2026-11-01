// All display formatting lives here. Every time is rendered in UTC
// (equal to UK local time in January), never in the browser's timezone.
const nf0 = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const timeFmt = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: 'UTC' });
const dateFmt = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const dayMonthFmt = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });

export const DASH = '—';
const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const ymd = (s) => new Date(`${s}T00:00:00Z`);

export const fmtMw = (v) => (isNum(v) ? nf0.format(v) : DASH);
export const fmtPct = (v) => (isNum(v) ? `${nf1.format(v)}%` : DASH);
export const fmtHours = (v) => (isNum(v) ? nf1.format(v) : DASH);

export function fmtSignedMw(v) {
  if (!isNum(v)) return DASH;
  const r = Math.round(v);
  if (r === 0) return '0';
  return `${r > 0 ? '+' : '−'}${nf0.format(Math.abs(r))}`;
}

export const fmtTime = (isoOrMs) => timeFmt.format(new Date(isoOrMs));
export const fmtDate = (iso) => dateFmt.format(new Date(iso));
export const fmtDayTime = (iso) => `${dayMonthFmt.format(new Date(iso))} ${timeFmt.format(new Date(iso))}`;
export const fmtDateOnly = (s) => dateFmt.format(ymd(s));
export const fmtDayMonthOnly = (s) => dayMonthFmt.format(ymd(s));

export function addDays(s, n) {
  const d = ymd(s);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export const isDateString = (s) => /^\d{4}-\d{2}-\d{2}$/.test(s ?? '') && !Number.isNaN(ymd(s).getTime());
export const inRange = (s, from, to) => isDateString(s) && s >= from && s <= to;

export function biasWord(bias) {
  if (!isNum(bias) || Math.round(bias) === 0) return 'no consistent direction';
  return bias > 0 ? 'forecasts ran high' : 'forecasts ran low';
}

export function leadLabel(bucket) {
  return bucket.bucket_end_h == null
    ? `${bucket.bucket_start_h}+ h`
    : `${bucket.bucket_start_h}–${bucket.bucket_end_h} h`;
}
