import { createContext, useContext } from 'react';

export const ConfigContext = createContext(null);
export const useConfig = () => useContext(ConfigContext);

export const PRODUCT_NAME = 'Wind Forecast Analytics';

/** Cutoff comes from the URL, falls back to the server default if absent or unknown. */
export function readCutoff(route, config) {
  const wanted = route.params.get('cutoff');
  return config.cutoff_options_utc.includes(wanted) ? wanted : config.default_cutoff_utc;
}
