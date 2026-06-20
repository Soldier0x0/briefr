/** CVE count → heatmap fill colour (theme tokens in App.css). */
export function heatmapColor(count) {
  if (!count || count <= 0) return 'var(--heatmap-0)'
  if (count <= 5) return 'var(--heatmap-1)'
  if (count <= 15) return 'var(--heatmap-2)'
  if (count <= 30) return 'var(--heatmap-3)'
  return 'var(--heatmap-4)'
}

export const HEATMAP_LEGEND_COUNTS = [0, 3, 10, 22, 40]

function parseUtcDate(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d))
}

function formatUtcDate(d) {
  return d.toISOString().slice(0, 10)
}

/**
 * Build a 7 × weekCount grid (rows = Sun–Sat, columns = weeks) for GitHub-style heatmap.
 * Window ends on today (UTC) so recent days are never truncated by a fixed column count.
 */
export function buildHeatmapGrid(timeline, displayDays, weekCount) {
  const byDate = Object.fromEntries(timeline.map(row => [row.date, row]))

  const end = parseUtcDate(formatUtcDate(new Date()))
  const start = new Date(end)
  start.setUTCDate(start.getUTCDate() - (displayDays - 1))

  const gridStart = new Date(start)
  gridStart.setUTCDate(gridStart.getUTCDate() - gridStart.getUTCDay())

  const msPerDay = 86400000
  const daysInGrid = Math.floor((end - gridStart) / msPerDay) + 1
  const columns = Math.max(weekCount, Math.ceil(daysInGrid / 7))

  const grid = Array.from({ length: 7 }, () => Array(columns).fill(null))
  const cursor = new Date(gridStart)

  for (let col = 0; col < columns; col++) {
    for (let row = 0; row < 7; row++) {
      const key = formatUtcDate(cursor)
      if (cursor >= start && cursor <= end) {
        const entry = byDate[key]
        grid[row][col] = {
          date: key,
          count: entry?.count ?? 0,
          critical: entry?.critical ?? 0,
          kev: entry?.kev ?? 0,
        }
      }
      cursor.setUTCDate(cursor.getUTCDate() + 1)
    }
  }

  return grid
}

/** Week columns needed for displayDays plus Sunday-alignment padding (max 6 days). */
export function weekCountForDays(displayDays) {
  return Math.ceil((displayDays + 6) / 7)
}
