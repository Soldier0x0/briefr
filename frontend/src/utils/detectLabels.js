/**
 * Sentence-case confidence label for generated detection hunt starters.
 * @param {string | null | undefined} raw e.g. LOW, MEDIUM, HIGH
 */
export function confidenceMatchLabel(raw) {
  const key = String(raw || 'MEDIUM').toUpperCase()
  const words = { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High' }
  const word = words[key] || (key.charAt(0) + key.slice(1).toLowerCase())
  return `${word} confidence match`
}

const COMPOSE_BASIS_LABELS = {
  community: 'Community rules',
  nuclei_artifacts: 'Nuclei / artifacts',
  yara: 'YARA hashes',
  template_fallback: 'Template fallback',
  none: 'Template fallback',
}

const COMPOSE_BASIS_TOOLTIPS = {
  community:
    'Community Sigma/Elastic rules were found for this CVE — they remain the primary deployable detections. Generated templates below are supplements.',
  nuclei_artifacts:
    'Composed from Nuclei templates and/or cached detection artifacts (paths, params, keywords). No LLM on this request path.',
  yara:
    'Primary evidence is YARA hash observables from linked OTX pulses. Tune before production use.',
  template_fallback:
    'No community rules or artifact evidence — emitting class/ATT&CK template keywords only. Higher false-positive risk.',
  none:
    'No community rules or artifact evidence — emitting class/ATT&CK template keywords only. Higher false-positive risk.',
}

/**
 * Human label for DC-2 compose_basis / evidence primary_source.
 * @param {string | null | undefined} basis
 */
export function composeBasisLabel(basis) {
  const key = String(basis || 'template_fallback').toLowerCase()
  return COMPOSE_BASIS_LABELS[key] || key.replace(/_/g, ' ')
}

/**
 * Discoverable explanation for compose_basis badges.
 * @param {string | null | undefined} basis
 */
export function composeBasisTooltip(basis) {
  const key = String(basis || 'template_fallback').toLowerCase()
  return COMPOSE_BASIS_TOOLTIPS[key] || COMPOSE_BASIS_TOOLTIPS.template_fallback
}

/**
 * One-line evidence pack summary for Detect framing.
 * @param {object | null | undefined} evidence
 * @returns {string | null}
 */
export function formatEvidenceSummary(evidence) {
  const summary = evidence?.evidence_summary
  if (!summary || typeof summary !== 'object') return null
  const primary = composeBasisLabel(summary.primary_source)
  const community = Number(summary.community_count) || 0
  const artifacts = Number(summary.artifact_count) || 0
  const nuclei = Number(summary.nuclei_count) || 0
  return `Primary: ${primary} · community ${community} · artifacts ${artifacts} · nuclei ${nuclei}`
}
