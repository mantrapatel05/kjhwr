import { api, useApi } from './lib/api.js';
import { ConfigContext } from './lib/config.js';
import { useRoute } from './lib/router.js';
import { Shell } from './components/Shell.jsx';
import { EmptyState, ErrorBoundary, ErrorState, Skeleton } from './components/States.jsx';
import Overview from './pages/Overview.jsx';
import DayExplorer from './pages/DayExplorer.jsx';
import LeadTime from './pages/LeadTime.jsx';
import Method from './pages/Method.jsx';

const PAGES = { '/': Overview, '/day': DayExplorer, '/lead-time': LeadTime, '/method': Method };

function NotFound() {
  return (
    <EmptyState title="Page not found">
      <a href="#/">Go to the overview</a>
    </EmptyState>
  );
}

export default function App() {
  const route = useRoute();
  const config = useApi(api.config());

  if (config.status === 'error') {
    return (
      <main className="page">
        <ErrorState title="The dashboard could not start" error={config.error} onRetry={config.retry} />
      </main>
    );
  }
  if (config.status !== 'success') {
    return (
      <main className="page">
        <Skeleton variant="page" label="Loading dashboard" />
      </main>
    );
  }

  const Page = PAGES[route.path] ?? NotFound;
  return (
    <ConfigContext.Provider value={config.data}>
      <Shell route={route} config={config.data}>
        <ErrorBoundary key={route.path}>
          <Page route={route} />
        </ErrorBoundary>
      </Shell>
    </ConfigContext.Provider>
  );
}
