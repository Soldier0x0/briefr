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
        mod.Legend,
        mod.Tooltip,
        mod.Filler,
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
    text: pick('--text2'),
    textMuted: pick('--text3'),
    grid: pick('--border'),
    red: pick('--red'),
    amber: pick('--amber'),
    accent: pick('--accent'),
    green: pick('--green'),
    mono: pick('--font-mono') || "'IBM Plex Mono', monospace",
  }
}
