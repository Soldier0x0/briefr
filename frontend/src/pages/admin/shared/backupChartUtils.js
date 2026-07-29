/** 1-based ordinal X-axis label (no dates on the chart axis). */
export function backupChartOrdinalLabel(index, total) {
  const n = Number(index)
  if (!Number.isFinite(n) || n < 0) return ''
  return String(n + 1)
}

export const BACKUP_CHART_LIMIT = 30

/**
 * Split backup rows for chart (oldest→newest, left→right) vs table (newest first).
 */
export function backupSizeRows(backups) {
  const rows = Array.isArray(backups) ? backups : []
  const newestFirst = [...rows].sort((a, b) =>
    String(b.created_at).localeCompare(String(a.created_at)),
  )
  const limited = newestFirst.slice(0, BACKUP_CHART_LIMIT)
  const chartRows = [...limited].reverse()
  const tableRows = limited
  return { chartRows, tableRows }
}

/**
 * Build LineChart rows with a guaranteed-unique categorical X key.
 *
 * Recharts axis tooltips look up by XAxis dataKey. Truncating filenames to
 * `briefr-20260…` made every point share one key, so hovering the far-right
 * (~95 MB) point still showed the far-left archive (50.3 MB).
 * Use the row index as pointKey; keep filename only for display/tooltip.
 */
export function backupChartPoints(rows, scale) {
  const total = (rows || []).length
  return (rows || []).map((row, index) => {
    const filename = row?.filename || `backup-${index}`
    return {
      pointKey: index,
      tickLabel: backupChartOrdinalLabel(index, total),
      size: scale.toDisplay(row?.size_bytes || 0),
      filename,
      created_at: row?.created_at,
    }
  })
}

/** Pure tooltip model from an active Recharts payload (for tests + renderer). */
export function backupTooltipModel(payload) {
  const point = Array.isArray(payload) ? payload[0]?.payload : null
  if (!point) return null
  return {
    filename: point.filename || '',
    size: Number(point.size) || 0,
  }
}
