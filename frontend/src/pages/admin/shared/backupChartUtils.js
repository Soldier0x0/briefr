/**
 * Short X-axis tick for a backup archive. Prefer the timestamp embedded in
 * the filename so adjacent archives stay visually distinct.
 */
export function backupChartTickLabel(filename) {
  const raw = String(filename || '')
  const stamp = raw.match(/(\d{8}T\d{6}Z?)/)?.[1]
  if (stamp) {
    const m = stamp.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})/)
    if (m) return `${m[2]}-${m[3]} ${m[4]}:${m[5]}`
    return stamp
  }
  const name = raw
    .replace(/^briefr-backup-/, '')
    .replace(/\.tar\.gz(?:\.age)?$/i, '')
  if (!name) return 'backup'
  return name.length > 12 ? `${name.slice(0, 12)}…` : name
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
  return (rows || []).map((row, index) => {
    const filename = row.filename || `backup-${index}`
    return {
      pointKey: index,
      tickLabel: backupChartTickLabel(filename),
      size: scale.toDisplay(row.size_bytes || 0),
      filename,
      created_at: row.created_at,
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
