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
  sigmahq_index: 'SigmaHQ index',
  nuclei_artifacts: 'Nuclei / artifacts',
  yara: 'YARA hashes',
  template_fallback: 'Template fallback',
  none: 'Template fallback',
}

const COMPOSE_BASIS_TOOLTIPS = {
  community:
    'Community Sigma/Elastic rules were found for this CVE — they remain the primary deployable detections. Generated templates below are supplements.',
  sigmahq_index:
    'CVE-exact Sigma rule from the local SigmaHQ Postgres index (DRL-1.1). Prefer this YAML over BRIEFR hunt starters.',
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

/**
 * Honest empty copy when Detect has no Sigma/Elastic community rules.
 * Distinguishes index-never-synced / empty index / CVE-exact miss.
 * @param {object | null | undefined} detection
 * @returns {string}
 */
export function communityRulesEmptyMessage(detection) {
  const idx = detection?.sigmahq_index
  const active = Number(idx?.rules_active) || 0
  if (active > 0) {
    return '// No CVE-exact SigmaHQ rule in the local index for this CVE (and no Elastic community hit)'
  }
  if (idx && !idx.synced_at) {
    return '// SigmaHQ index not synced yet — run Sync from Admin → Feed health. Until then there are no local community Sigma rules; many CVEs also have none upstream.'
  }
  if (idx && active === 0) {
    return '// SigmaHQ index is empty (0 active rules) — check Admin → Feed health / Force re-sync. No community Sigma/Elastic rules for this CVE.'
  }
  return '// No community Sigma/Elastic rules found for this CVE'
}
