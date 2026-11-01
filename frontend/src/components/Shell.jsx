import { useEffect, useRef } from 'react';
import { PRODUCT_NAME } from '../lib/config.js';
import { buildHash } from '../lib/router.js';
import { fmtDate } from '../lib/format.js';

export const NAV = [
  { path: '/', label: 'Overview', title: 'Forecast accuracy' },
  { path: '/day', label: 'Day', title: 'Day explorer' },
  { path: '/lead-time', label: 'Lead time', title: 'Accuracy by forecast age' },
  { path: '/method', label: 'Method', title: 'Method' },
];

export function Shell({ route, config, children }) {
  const mainRef = useRef(null);
  const current = NAV.find((n) => n.path === route.path);
  const title = current ? current.title : 'Page not found';
  const cutoff = route.params.get('cutoff');

  useEffect(() => {
    document.title = `${title} · ${PRODUCT_NAME}`;
    window.scrollTo(0, 0);
  }, [title, route.path]);

  const skip = (e) => {
    e.preventDefault();
    mainRef.current?.focus();
  };

  return (
    <>
      <a className="skip-link" href="#main" onClick={skip}>Skip to content</a>
      <header className="app-header">
        <div className="app-header__inner">
          <p className="brand">{PRODUCT_NAME}</p>
          <nav className="nav" aria-label="Primary">
            <ul className="nav__list">
              {NAV.map((n) => (
                <li key={n.path}>
                  <a className="nav__link" href={buildHash(n.path, { cutoff })} aria-current={n.path === route.path ? 'page' : undefined}>
                    {n.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>
      <p className="sr-only" role="status">{title}</p>
      <main id="main" ref={mainRef} tabIndex={-1} className="page">
        {children}
      </main>
      <footer className="app-footer">
        <p>
          Source: Elexon Insights API (FUELHH actuals, WINDFOR forecasts), used under the BMRS Data Licence.
          {config?.snapshot_fetched_at ? ` Data snapshot fetched ${fmtDate(config.snapshot_fetched_at)}.` : ''}
          {' '}All times are UTC.
        </p>
      </footer>
    </>
  );
}
