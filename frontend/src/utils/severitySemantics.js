/** CVSS severity scale — shared copy for legends and portaled tooltips (E4-4). */

export const SEVERITY_LEVELS = [
  {
    id: 'critical',
    label: 'CRITICAL',
    className: 'critical',
    desc: 'CVSS 9.0–10.0 — maximum technical impact; prioritize remediation.',
  },
  {
    id: 'high',
    label: 'HIGH',
    className: 'high',
    desc: 'CVSS 7.0–8.9 — significant impact on confidentiality, integrity, or availability.',
  },
  {
    id: 'medium',
    label: 'MEDIUM',
    className: 'medium',
    desc: 'CVSS 4.0–6.9 — moderate impact.',
  },
  {
    id: 'low',
    label: 'LOW',
    className: 'low',
    desc: 'CVSS 0.1–3.9 — limited impact.',
  },
  {
    id: 'unknown',
    label: 'UNKNOWN',
    className: 'neutral',
    desc: 'No CVSS base score assigned yet.',
  },
]

const SEVERITY_BY_ID = Object.fromEntries(SEVERITY_LEVELS.map((row) => [row.id, row]))

/** Compact visible label for color+text pairs (E6-5 color-not-alone). */
export function severityShortLabel(severity) {
  const key = (severity || 'unknown').toLowerCase()
  const row = SEVERITY_BY_ID[key] || SEVERITY_BY_ID.unknown
  return row.label
}

export function severityTooltip(severity, cvssScore = null) {
  const key = (severity || 'unknown').toLowerCase()
  const row = SEVERITY_BY_ID[key] || SEVERITY_BY_ID.unknown
  const score = cvssScore !== null && cvssScore !== undefined ? Number(cvssScore) : null
  if (score !== null && Number.isFinite(score)) {
    return `CVSS ${score} (${row.label}) — ${row.desc}`
  }
  return `${row.label} — ${row.desc}`
}

export const FORGE_STATUS_TOOLTIPS = {
  gap: 'Technique with no detection content — no bundled or saved hunt pack yet.',
  community: 'Community hunt templates available — validate before production use.',
  yours: 'Hunt pack you have saved for this technique.',
}

export function forgeStatusTooltip(status) {
  return FORGE_STATUS_TOOLTIPS[status] || String(status || '')
}
