import { useEffect, useState } from 'react';

// Hash routing: no server-side fallback needed on Vercel or Heroku.
export function parseHash(hash) {
  const raw = hash.replace(/^#/, '') || '/';
  const [path, query = ''] = raw.split('?');
  return { path: path || '/', params: new URLSearchParams(query) };
}

export function buildHash(path, params = {}) {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== '') sp.set(k, v);
  }
  const q = sp.toString();
  return `#${path}${q ? `?${q}` : ''}`;
}

export function navigate(path, params) {
  window.location.hash = buildHash(path, params);
}

export function useRoute() {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return route;
}
