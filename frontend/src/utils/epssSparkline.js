const SPARK_W = 200
const SPARK_H = 40
const PAD = 3

/** @typedef {{ date: string, score: number }} EpssPoint */

/**
 * @param {EpssPoint[]} history
 * @param {number | null | undefined} currentScore
 */
export function buildEpssSparklinePoints(history, currentScore) {
  let points = Array.isArray(history) ? [...history] : []
  const today = new Date().toISOString().slice(0, 10)

  if (currentScore != null && currentScore >= 0) {
    const last = points[points.length - 1]
    const lastDate = last ? String(last.date).slice(0, 10) : null
    if (lastDate === today) {
      points[points.length - 1] = { ...last, date: today, score: currentScore }
    } else {
      points.push({ date: today, score: currentScore })
    }
  } else if (!points.length) {
    return []
  }

  return points
    .filter(p => p && p.score != null && !Number.isNaN(Number(p.score)))
    .sort((a, b) => String(a.date).localeCompare(String(b.date)))
    .map(p => ({ date: String(p.date).slice(0, 10), score: Number(p.score) }))
}

/**
 * @param {EpssPoint[]} points
 * @returns {string | null} polyline points attribute
 */
export function epssSparklinePolyline(points) {
  if (!points.length) return null
  if (points.length === 1) {
    const y = SPARK_H / 2
    return `${PAD},${y} ${SPARK_W - PAD},${y}`
  }

  const scores = points.map(p => p.score)
  const min = Math.min(...scores)
  const max = Math.max(...scores)
  const range = max - min || 0.0001

  return points
    .map((p, i) => {
      const x = PAD + (i / (points.length - 1)) * (SPARK_W - PAD * 2)
      const y = SPARK_H - PAD - ((p.score - min) / range) * (SPARK_H - PAD * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

/**
 * Rising / Falling / Stable from >5% change over ~7 days.
 * @param {EpssPoint[]} points
 * @param {number | null | undefined} currentScore
 */
export function epssTrendLabel(points, currentScore) {
  const sorted = buildEpssSparklinePoints(points, currentScore)
  if (sorted.length < 2) {
    return { label: 'Stable', tone: 'stable' }
  }

  const latest = sorted[sorted.length - 1]
  const latestMs = Date.parse(`${latest.date}T12:00:00Z`)
  const targetMs = latestMs - 7 * 86400000

  let baseline = sorted[0]
  let bestDelta = Math.abs(Date.parse(`${baseline.date}T12:00:00Z`) - targetMs)
  for (const p of sorted) {
    const d = Math.abs(Date.parse(`${p.date}T12:00:00Z`) - targetMs)
    if (d < bestDelta) {
      bestDelta = d
      baseline = p
    }
  }

  if (baseline.date === latest.date) {
    return { label: 'Stable', tone: 'stable' }
  }

  const base = baseline.score
  if (base <= 0) {
    return { label: 'Stable', tone: 'stable' }
  }

  const change = (latest.score - base) / base
  if (change > 0.05) return { label: 'Rising', tone: 'rising' }
  if (change < -0.05) return { label: 'Falling', tone: 'falling' }
  return { label: 'Stable', tone: 'stable' }
}

export const EPSS_SPARKLINE_WIDTH = SPARK_W
export const EPSS_SPARKLINE_HEIGHT = SPARK_H
