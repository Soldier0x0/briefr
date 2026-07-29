import { bytesChartScale } from './formatters.js'

/**
 * Build Resource LineChart rows. HH:MM alone collides across days on
 * 3d/7d/30d windows and freezes the Recharts axis tooltip on the first
 * matching minute — use row index as the categorical X key.
 */
export function resourceChartPoints(plottable, fields, hostProfile = null) {
  const allBytes = fields.length > 0 && fields.every((field) => field.endsWith('_bytes'))
  const allPct = fields.length > 0 && fields.every((field) => field.endsWith('_pct'))
  const scale = allBytes
    ? bytesChartScale(
      plottable.flatMap((row) => fields.map((field) => Number(row[field]) || 0)),
    )
    : null

  let ceilingLine = null
  if (hostProfile?.memory_total_bytes && allBytes && fields.includes('briefr_rss_bytes')) {
    const memScale = bytesChartScale([hostProfile.memory_total_bytes])
    ceilingLine = memScale.toDisplay(hostProfile.memory_total_bytes)
  } else if (allPct) {
    ceilingLine = 100
  }

  const data = plottable.map((row, index) => {
    const entry = {
      pointKey: index,
      tsLabel: row.ts?.slice(11, 16) || '',
      tsFull: row.ts ? String(row.ts).slice(0, 19) : '—',
    }
    fields.forEach((field) => {
      const raw = row[field] != null ? Number(row[field]) : null
      if (raw == null || Number.isNaN(raw)) {
        entry[field] = null
      } else {
        entry[field] = scale ? scale.toDisplay(raw) : raw
      }
    })
    return entry
  })

  return { data, scale, ceilingLine }
}
