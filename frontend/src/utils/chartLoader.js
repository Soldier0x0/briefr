/** Lazy-load Chart.js once; registers only the controllers/scales we use. */

let chartPromise = null

export function loadChartJs() {
  if (!chartPromise) {
    chartPromise = import('chart.js').then((mod) => {
      mod.Chart.register(
        mod.CategoryScale,
        mod.LinearScale,
        mod.BarController,
        mod.BarElement,
        mod.LineController,
        mod.LineElement,
        mod.PointElement,
        mod.Filler,
        mod.Legend,
        mod.Tooltip,
      )
      return mod.Chart
    })
  }
  return chartPromise
}

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
  }
}
