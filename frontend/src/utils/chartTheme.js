/** Read semantic chart colors from CSS custom properties. */

export function readChartTheme() {
  const root = document.documentElement
  const style = getComputedStyle(root)
  const pick = (name) => style.getPropertyValue(name).trim()
  return {
    text: pick('--text'),
    textSecondary: pick('--text2'),
    textMuted: pick('--text3'),
    grid: pick('--border'),
    panel: pick('--bg2'),
    red: pick('--red'),
    redDim: pick('--red-dim'),
    amber: pick('--amber'),
    amberDim: pick('--amber-dim'),
    accent: pick('--accent'),
    green: pick('--green'),
    greenDim: pick('--green-dim'),
    mono: pick('--font-mono') || "'IBM Plex Mono', monospace",
    sans: pick('--font-sans') || "'IBM Plex Sans', system-ui, sans-serif",
    chart1: pick('--chart-1') || pick('--accent'),
    chart2: pick('--chart-2') || pick('--text2'),
    surfaceSelected: pick('--surface-selected') || pick('--chip-active-bg'),
    borderStrong: pick('--border-strong') || pick('--border'),
  }
}
