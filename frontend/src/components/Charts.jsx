import { useMemo } from 'react';
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { readChartTheme } from '../lib/tokens.js';
import { buildChartRows, buildErrorRows, chartAxis } from '../lib/series.js';
import { fmtDayMonthOnly, fmtMw, fmtSignedMw, fmtTime } from '../lib/format.js';

const useTheme = () => useMemo(readChartTheme, []);

function axisStyle(theme) {
  return {
    tick: { fontSize: theme.fontSize, fill: theme.tick },
    tickLine: false,
    axisLine: { stroke: theme.axis },
  };
}

export function Legend({ items }) {
  return (
    <ul className="legend">
      {items.map((i) => (
        <li key={i.label} className="legend__item">
          <span className={`swatch swatch--${i.kind}`} aria-hidden="true" />
          {i.label}
        </li>
      ))}
    </ul>
  );
}

function Figure({ title, unit, legend, summary, children }) {
  return (
    <figure className="chart">
      <figcaption className="chart__head">
        <span className="chart__title">{title}</span>
        <Legend items={legend} />
      </figcaption>
      <p className="chart__unit">{unit}</p>
      <div className="chart__plot" role="group" aria-label={summary}>{children}</div>
    </figure>
  );
}

function Tip({ title, lines }) {
  return (
    <div className="tooltip">
      <p className="tooltip__title">{title}</p>
      <dl className="tooltip__list">
        {lines.map(([k, v]) => (
          <div key={k} className="tooltip__row"><dt>{k}</dt><dd className="num">{v}</dd></div>
        ))}
      </dl>
    </div>
  );
}

function LevelTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <Tip
      title={`${fmtTime(row.t)} UTC`}
      lines={[['Forecast', `${fmtMw(row.forecast)} MW`], ['Actual', `${fmtMw(row.actual)} MW`]]}
    />
  );
}

function ErrorTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return <Tip title={`${row.label} UTC`} lines={[['Forecast minus actual', `${fmtSignedMw(row.error)} MW`]]} />;
}

export function ForecastChart({ points, actualsOnly, deliveryDay }) {
  const theme = useTheme();
  const { rows, segmentKeys } = useMemo(() => buildChartRows(points, actualsOnly), [points, actualsOnly]);
  const { domain, ticks } = useMemo(() => chartAxis(deliveryDay), [deliveryDay]);
  return (
    <Figure
      title="Forecast and actual generation"
      unit="MW, by delivery time (UTC)"
      legend={[{ kind: 'forecast', label: 'Forecast known at cutoff' }, { kind: 'actual', label: 'Actual' }]}
      summary="Line chart of the forecast known at the cutoff and actual wind generation across the delivery day. The same values are in the table below."
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} accessibilityLayer>
          <CartesianGrid vertical={false} stroke={theme.grid} />
          <XAxis dataKey="t" type="number" scale="time" domain={domain} ticks={ticks} tickFormatter={fmtTime} {...axisStyle(theme)} />
          <YAxis width={48} domain={[0, 'auto']} tickFormatter={fmtMw} {...axisStyle(theme)} />
          <Tooltip content={<LevelTooltip />} cursor={{ stroke: theme.axis }} isAnimationActive={false} />
          <Line dataKey="actual" name="Actual" stroke={theme.actual} strokeWidth={2} dot={false} activeDot={{ r: 4 }} connectNulls={false} isAnimationActive={false} />
          {segmentKeys.map((k) => (
            <Line key={k} dataKey={k} stroke={theme.forecast} strokeWidth={2} dot={{ r: 3, fill: theme.forecast, strokeWidth: 0 }} activeDot={{ r: 5 }} connectNulls isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Figure>
  );
}

export function ErrorChart({ points, p90 }) {
  const theme = useTheme();
  const rows = useMemo(() => buildErrorRows(points), [points]);
  const hasBuffer = typeof p90 === 'number';
  const bufferLabel = { value: `P90 ${fmtMw(p90)} MW (period)`, position: 'insideTopRight', fill: theme.tick, fontSize: theme.fontSize };
  return (
    <Figure
      title="Forecast error"
      unit="MW, forecast minus actual"
      legend={[
        { kind: 'over', label: 'Above zero: forecast too high' },
        { kind: 'under', label: 'Below zero: forecast too low' },
      ]}
      summary="Bar chart of forecast minus actual for each interval of the delivery day. Dashed lines mark the period P90 absolute error."
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} accessibilityLayer>
          <CartesianGrid vertical={false} stroke={theme.grid} />
          <XAxis dataKey="label" interval="preserveStartEnd" minTickGap={16} {...axisStyle(theme)} />
          <YAxis width={56} tickFormatter={fmtSignedMw} {...axisStyle(theme)} />
          <ReferenceLine y={0} stroke={theme.muted} />
          {hasBuffer && <ReferenceLine y={p90} stroke={theme.axis} strokeDasharray="4 4" ifOverflow="extendDomain" label={bufferLabel} />}
          {hasBuffer && <ReferenceLine y={-p90} stroke={theme.axis} strokeDasharray="4 4" ifOverflow="extendDomain" />}
          <Tooltip content={<ErrorTooltip />} cursor={{ fill: theme.sunken }} isAnimationActive={false} />
          <Bar dataKey="error" maxBarSize={16} isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.t} fill={r.error !== null && r.error < 0 ? theme.under : theme.over} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Figure>
  );
}

function DailyTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <Tip
      title={`Decision ${fmtDayMonthOnly(d.decision_date)}`}
      lines={[['MAE', `${fmtMw(d.mae_mw)} MW`], ['Matched intervals', String(d.n)]]}
    />
  );
}

export function DailyChart({ days, periodMae, onSelect }) {
  const theme = useTheme();
  return (
    <Figure
      title="Mean absolute error by decision date"
      unit="MW"
      legend={[{ kind: 'bar', label: 'MAE for that day' }]}
      summary="Bar chart of mean absolute error for each decision date. Select a bar, or use the table below, to open that day."
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={days} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} accessibilityLayer>
          <CartesianGrid vertical={false} stroke={theme.grid} />
          <XAxis dataKey="decision_date" tickFormatter={fmtDayMonthOnly} minTickGap={16} {...axisStyle(theme)} />
          <YAxis width={48} tickFormatter={fmtMw} {...axisStyle(theme)} />
          {typeof periodMae === 'number' && (
            <ReferenceLine y={periodMae} stroke={theme.axis} strokeDasharray="4 4" ifOverflow="extendDomain" label={{ value: `Period MAE ${fmtMw(periodMae)} MW`, position: 'insideTopRight', fill: theme.tick, fontSize: theme.fontSize }} />
          )}
          <Tooltip content={<DailyTooltip />} cursor={{ fill: theme.sunken }} isAnimationActive={false} />
          <Bar dataKey="mae_mw" fill={theme.error} maxBarSize={20} className="is-clickable" isAnimationActive={false} onClick={(d) => onSelect(d.decision_date ?? d.payload?.decision_date)} />
        </BarChart>
      </ResponsiveContainer>
    </Figure>
  );
}

function LeadTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <Tip
      title={d.label}
      lines={[['MAE', `${fmtMw(d.mae_mw)} MW`], ['RMSE', `${fmtMw(d.rmse_mw)} MW`], ['Matched pairs', String(d.n)]]}
    />
  );
}

export function LeadChart({ buckets }) {
  const theme = useTheme();
  return (
    <Figure
      title="MAE and RMSE by lead time"
      unit="MW, by lead time (hours between publication and delivery)"
      legend={[{ kind: 'mae', label: 'MAE' }, { kind: 'rmse', label: 'RMSE' }]}
      summary="Line chart of MAE and RMSE by lead time bucket. The same values are in the table below."
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={buckets} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} accessibilityLayer>
          <CartesianGrid vertical={false} stroke={theme.grid} />
          <XAxis dataKey="label" {...axisStyle(theme)} />
          <YAxis width={48} domain={[0, 'auto']} tickFormatter={fmtMw} {...axisStyle(theme)} />
          <Tooltip content={<LeadTooltip />} cursor={{ stroke: theme.axis }} isAnimationActive={false} />
          <Line dataKey="mae_mw" stroke={theme.error} strokeWidth={2} dot={{ r: 3, fill: theme.error, strokeWidth: 0 }} activeDot={{ r: 5 }} isAnimationActive={false} />
          <Line dataKey="rmse_mw" stroke={theme.error} strokeWidth={2} strokeDasharray="6 4" dot={false} activeDot={{ r: 5 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </Figure>
  );
}
