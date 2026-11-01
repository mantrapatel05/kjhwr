import { useCallback, useEffect, useState } from 'react';

const BASE = import.meta.env.VITE_API_BASE ?? '';

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function getJson(path, signal) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, { signal, headers: { Accept: 'application/json' } });
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    throw new ApiError('Could not reach the server.', 0);
  }
  if (!res.ok) {
    let detail;
    try {
      const body = await res.json();
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      /* body was not JSON */
    }
    throw new ApiError(detail ?? `The server returned an error (${res.status}).`, res.status);
  }
  return res.json();
}

const q = (params) => new URLSearchParams(params).toString();

// One function per endpoint in the backend contract (05_ARCHITECTURE_AND_API.md).
export const api = {
  config: () => '/api/config',
  forecastVsActual: (decisionDate, cutoff) => `/api/forecast-vs-actual?${q({ decision_date: decisionDate, cutoff })}`,
  versions: (targetTime, cutoffUtc) => `/api/forecast-versions?${q({ target_time: targetTime, cutoff: cutoffUtc })}`,
  metrics: (from, to, cutoff) => `/api/metrics?${q({ from, to, cutoff })}`,
  daily: (cutoff) => `/api/metrics/daily?${q({ cutoff })}`,
  byLeadTime: (bucketHours = 6) => `/api/metrics/by-lead-time?${q({ bucket_hours: bucketHours })}`,
};

const cache = new Map();

/**
 * Server state for one GET url. Returns { status, data, error, retry }.
 * status: 'idle' (url is null) | 'loading' | 'success' | 'error'.
 * Results are cached per url for the session; retry bypasses the cache.
 */
export function useApi(url) {
  const [result, setResult] = useState({ url: null });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!url || cache.has(url)) return undefined;
    const controller = new AbortController();
    getJson(url, controller.signal)
      .then((data) => {
        cache.set(url, data);
        setResult({ url, status: 'success', data });
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setResult({ url, status: 'error', error });
      });
    return () => controller.abort();
  }, [url, nonce]);

  const retry = useCallback(() => {
    cache.delete(url);
    setResult({ url, status: 'loading' });
    setNonce((n) => n + 1);
  }, [url]);

  let current;
  if (!url) current = { status: 'idle' };
  else if (cache.has(url)) current = { status: 'success', data: cache.get(url) };
  else if (result.url === url) current = result;
  else current = { status: 'loading' };

  return { ...current, retry };
}

export function clearApiCache() {
  cache.clear();
}
