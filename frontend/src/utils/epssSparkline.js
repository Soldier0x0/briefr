const SPARK_W = 200
const SPARK_H = 40
const PAD = 3

export const EPSS_SPARKLINE_MIN_DAYS = 7
/** Days of daily EPSS context when the selected change window is shorter than a week. */
export const EPSS_CONTEXT_DAYS = 7

/** @typedef {{ date: string, score: number }} EpssPoint */

/**
 * Map a change-window (hours) to sparkline length + column copy.
 * EPSS updates about once per day, so sub-week windows get a labeled
 * recent-daily context series while Delta still uses the selected window.
 *
 * @param {number | null | undefined} windowHours
 * @returns {{ days: number, isContext: boolean, columnLabel: string, columnTooltip: string }}
 */
function epssContextWindowSpec() {
  return {
    days: EPSS_CONTEXT_DAYS,
    isContext: true,
    columnLabel: `${EPSS_CONTEXT_DAYS}d context`,
    columnTooltip:
      'EPSS updates about once per day, so this sparkline shows recent daily scores for context. Delta still uses the selected time window.',
  }
}

export function epssSparklineWindowSpec(windowHours) {
  const hours = Number(windowHours)
  if (!Number.isFinite(hours) || hours <= 0) {
    return epssContextWindowSpec()
  }

  const requestedDays = Math.max(1, Math.ceil(hours / 24))
  if (requestedDays < EPSS_CONTEXT_DAYS) {
    return epssContextWindowSpec()
  }

  return {
    days: requestedDays,
    isContext: false,
    columnLabel: `${requestedDays}d trend`,
    columnTooltip: `Daily EPSS scores over the last ${requestedDays} days.`,
  }
}

/**
 * Keep history points inside the trailing `days` calendar-day window ending at `asOf`.
 *
 * @param {EpssPoint[] | null | undefined} history
 * @param {number} days
 * @param {{ asOf?: Date | string | number }} [opts]
 * @returns {EpssPoint[]}
 */
export function filterEpssHistoryToDays(history, days, { asOf = new Date() } = {}) {
  if (!Array.isArray(history) || !history.length) return []
  const n = Math.max(1, Number(days) || EPSS_CONTEXT_DAYS)
  const end = asOf instanceof Date ? asOf : new Date(asOf)
  if (Number.isNaN(end.getTime())) return [...history]
  const endDate = end.toISOString().slice(0, 10)
  const startMs = Date.parse(`${endDate}T12:00:00Z`) - (n - 1) * 86400000
  const startDate = new Date(startMs).toISOString().slice(0, 10)
  return history.filter((p) => {
    const d = String(p?.date || '').slice(0, 10)
    return d.length === 10 && d >= startDate && d <= endDate
  })
}

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

/** @param {EpssPoint[]} points */
export function hasEnoughEpssHistory(points) {
  return Array.isArray(points) && points.length >= EPSS_SPARKLINE_MIN_DAYS
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
 * Rising / Falling / Stable from absolute EPSS change vs ~7 days ago.
 * @param {EpssPoint[]} points
 * @param {number | null | undefined} currentScore
 */
export function epssTrendLabel(points, currentScore) {
  const sorted = buildEpssSparklinePoints(points, currentScore)
  if (sorted.length < 2) {
    return { label: 'Stable', tone: 'stable' }
  }

  const latest = sorted[sorted.length - 1]
  const current = latest.score
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

  const change = current - baseline.score
  if (change > 0.05) return { label: 'Rising', tone: 'rising' }
  if (change < -0.05) return { label: 'Falling', tone: 'falling' }
  return { label: 'Stable', tone: 'stable' }
}

/** True when the series has enough day-over-day movement to justify a sparkline. */
export function hasMeaningfulEpssVariation(points, minDelta = 0.02) {
  if (!Array.isArray(points) || points.length < 2) return false
  const scores = points.map(p => p.score)
  return Math.max(...scores) - Math.min(...scores) >= minDelta
}

export const EPSS_SPARKLINE_WIDTH = SPARK_W
export const EPSS_SPARKLINE_HEIGHT = SPARK_H
