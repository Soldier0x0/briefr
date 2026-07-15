/** Lazy-load Chart.js once; registers only the controllers/scales we use. */

export { readChartTheme } from './chartTheme.js'

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
