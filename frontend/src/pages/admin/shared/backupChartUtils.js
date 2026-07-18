/**
 * Short X-axis tick for a backup archive. Prefer the timestamp embedded in
 * the filename so adjacent archives stay visually distinct (truncating
 * `briefr-202607…` collapses every point to the same category key and
 * freezes the Recharts tooltip on the first match).
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

export function backupChartPoints(rows, scale) {
  return (rows || []).map((row, index) => {
    const filename = row.filename || `backup-${index}`
    return {
      // Unique categorical key — never truncate this; Recharts tooltip/lookup
      // keys off XAxis dataKey and duplicate labels pin every hover to row 0.
      pointKey: filename,
      tickLabel: backupChartTickLabel(filename),
      size: scale.toDisplay(row.size_bytes || 0),
      filename,
      created_at: row.created_at,
    }
  })
}
