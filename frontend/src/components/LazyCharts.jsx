import { lazy, Suspense } from 'react';
import { Skeleton } from './States.jsx';

// Recharts is the heaviest dependency, so charts load in their own chunk.
function lazyChart(name) {
  const Chart = lazy(() => import('./Charts.jsx').then((m) => ({ default: m[name] })));
  return function LazyChart(props) {
    return (
      <Suspense fallback={<Skeleton variant="chart" label="Loading chart" />}>
        <Chart {...props} />
      </Suspense>
    );
  };
}

export const ForecastChart = lazyChart('ForecastChart');
export const ErrorChart = lazyChart('ErrorChart');
export const DailyChart = lazyChart('DailyChart');
export const LeadChart = lazyChart('LeadChart');
