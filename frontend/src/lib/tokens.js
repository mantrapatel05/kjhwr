// Chart libraries need concrete colours, so read them from the CSS tokens once.
const read = (style, name) => style.getPropertyValue(name).trim();

export function readChartTheme() {
  const s = getComputedStyle(document.documentElement);
  return {
    forecast: read(s, '--series-forecast'),
    actual: read(s, '--series-actual'),
    over: read(s, '--series-over'),
    under: read(s, '--series-under'),
    error: read(s, '--series-error'),
    grid: read(s, '--border'),
    axis: read(s, '--border-strong'),
    tick: read(s, '--text-subtle'),
    muted: read(s, '--text-muted'),
    sunken: read(s, '--surface-sunken'),
    fontSize: 12, // matches --text-xs (0.75rem)
  };
}
