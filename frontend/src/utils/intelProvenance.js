/**
 * FR1 — one provenance line per intel drawer section.
 */

const STATUS_LABELS = {
  checked: 'Checked',
  pending: 'Pending',
  source_unavailable: 'Source unavailable',
}

const STATUS_TOOLTIPS = {
  checked:
    'BRIEFR successfully queried this intelligence source for this CVE. Empty results mean no matching data was found — not that the check failed.',
  pending:
    'Enrichment for this section has not completed yet. Data may appear after the next sync or when you revisit this CVE.',
  source_unavailable:
    'The upstream source is not configured, rate-limited, or temporarily unavailable. Absence of data here does not mean there is no intelligence.',
}

/**
 * @param {object | null | undefined} provenance
 * @returns {string | null}
 */
export function formatIntelProvenanceLine(provenance) {
  if (!provenance || typeof provenance !== 'object') return null
  const status = String(provenance.status || 'pending').toLowerCase()
  const label = STATUS_LABELS[status] || STATUS_LABELS.pending
  const source = String(provenance.source || 'BRIEFR').trim()
  const asOf = provenance.as_of ? String(provenance.as_of).trim() : ''
  if (asOf) {
    return `As of ${asOf} · ${source} · ${label}`
  }
  return `${source} · ${label}`
}

/**
 * @param {object | null | undefined} provenance
 * @returns {string}
 */
export function intelProvenanceTooltip(provenance) {
  const status = String(provenance?.status || 'pending').toLowerCase()
  return STATUS_TOOLTIPS[status] || STATUS_TOOLTIPS.pending
}
