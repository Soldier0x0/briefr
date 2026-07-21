/**
 * Analyst-facing copy for correlation evidence and link strength.
 */

import { formatIntelLabelText } from './formatIntelLabel.js'

const IOC_TYPE_LABELS = {
  IP: 'IP',
  DOMAIN: 'Domain',
  HASH: 'Hash',
  URL: 'URL',
}

const CONFIRMATION_LABELS = {
  greynoise_malicious: 'GreyNoise malicious classification',
  malwarebazaar: 'MalwareBazaar sample match',
  urlhaus_active: 'URLhaus active distribution',
}

/** Analyst-facing lifecycle labels for feed campaign badges (C-Evolve-2). */
export const CAMPAIGN_LIFECYCLE_LABELS = {
  active: 'Active campaign',
  emerging: 'Emerging campaign',
  declining: 'Declining campaign',
  stale: 'Stale campaign',
}

/**
 * Discoverable tooltip for the feed "Campaign" badge (PRODUCT.md principle 1).
 * @param {string | null | undefined} lifecycle
 * @returns {string}
 */
export function campaignBadgeTooltip(lifecycle) {
  const key = String(lifecycle || 'active').toLowerCase()
  const label = CAMPAIGN_LIFECYCLE_LABELS[key] || 'Campaign cluster'
  if (key === 'active') {
    return `${label} — this CVE is grouped with related vulnerabilities in an OTX pulse cluster with recent KEV, PoC, or EPSS activity. Open the drawer for full correlation details.`
  }
  if (key === 'emerging') {
    return `${label} — newly linked to an OTX pulse cluster within the last week. Open the drawer for full correlation details.`
  }
  if (key === 'declining') {
    return `${label} — grouped in an OTX pulse cluster with no recent member activity (30+ days). Open the drawer for full correlation details.`
  }
  if (key === 'stale') {
    return `${label} — grouped in an older OTX pulse cluster (12+ months) without KEV or PoC boosters. Open the drawer for full correlation details.`
  }
  return `${label} — BRIEFR grouped this CVE with related vulnerabilities from shared OTX pulse intelligence. Open the drawer for full correlation details.`
}

/**
 * CSS modifier for lifecycle-specific badge styling.
 * @param {string | null | undefined} lifecycle
 * @returns {string}
 */
export function campaignLifecycleClass(lifecycle) {
  const key = String(lifecycle || 'active').toLowerCase()
  if (key === 'emerging') return 'badge-campaign-emerging'
  if (key === 'declining') return 'badge-campaign-declining'
  if (key === 'stale') return 'badge-campaign-stale'
  return 'badge-campaign-active'
}

/**
 * Primary campaign row for drawer header chip (C-Evolve-3).
 * @param {object | null | undefined} correlation
 * @param {string} cveId
 * @returns {{ campaign: object, linkedCount: number, lifecycle: string } | null}
 */
export function primaryCampaignChip(correlation, cveId) {
  const campaigns = correlation?.campaigns
  if (!Array.isArray(campaigns) || !campaigns.length || !cveId) return null
  const sorted = [...campaigns].sort((a, b) => {
    const countA = a.member_count ?? (a.members?.length ?? 0)
    const countB = b.member_count ?? (b.members?.length ?? 0)
    return countB - countA
  })
  const primary = sorted[0]
  const members = Array.isArray(primary.members) ? primary.members : []
  const linkedCount = members.filter(id => id && id !== cveId).length
  if (linkedCount <= 0) return null
  return {
    campaign: primary,
    linkedCount,
    lifecycle: primary.lifecycle || 'active',
  }
}

export const SUPPRESSION_REASONS = [
  { id: 'shared_hosting', label: 'Shared hosting / CDN' },
  { id: 'known_scanner', label: 'Known scanner' },
  { id: 'vendor_infrastructure', label: 'Vendor infrastructure' },
  { id: 'common_service', label: 'Common service' },
  { id: 'false_positive_ioc', label: 'False-positive IOC' },
  { id: 'other', label: 'Other' },
]

/**
 * CORR-PR-8: evidence freshness metadata for drawer staleness tint + timeline.
 * @param {object | null | undefined} ev
 * @returns {{ stale: boolean, timeline: string | null, title: string | null }}
 */
export function evidenceFreshnessMeta(ev) {
  if (!ev || typeof ev !== 'object') {
    return { stale: false, timeline: null, title: null }
  }
  const factor = ev.freshness_factor
  const stale = typeof factor === 'number' && factor < 0.5 && !ev.freshness_fallback
  const parts = []
  if (ev.observed_at) {
    parts.push(`Observed ${String(ev.observed_at).slice(0, 10)}`)
  }
  if (ev.ingested_at) {
    parts.push(`Ingested ${String(ev.ingested_at).slice(0, 10)}`)
  }
  const timeline = parts.length ? parts.join(' · ') : null
  const title = ev.freshness_reason || (
    ev.freshness_fallback
      ? 'Observation time unknown — staleness decay was not applied'
      : stale
        ? 'Shared indicator evidence is stale relative to its type half-life'
        : null
  )
  return { stale, timeline, title }
}

/**
 * @param {object[]} evidence
 * @returns {boolean}
 */
export function correlationEvidenceIsStale(evidence = []) {
  return evidence.some(ev => evidenceFreshnessMeta(ev).stale)
}

/**
 * @param {object} item — infrastructure or campaign correlation row
 * @returns {boolean}
 */
export function correlationItemIsStale(item) {
  const evidence = Array.isArray(item?.evidence) ? item.evidence : []
  return correlationEvidenceIsStale(evidence)
}

/**
 * @param {string} confidence
 * @param {{ stale?: boolean }} [opts]
 * @returns {string}
 */
export function confidenceBadgeClass(confidence, opts = {}) {
  const level = String(confidence || 'low').toLowerCase()
  const base =
    level === 'high'
      ? 'corr-badge-high'
      : level === 'medium'
        ? 'corr-badge-medium'
        : 'corr-badge-low'
  return opts.stale ? `${base} corr-badge-stale` : base
}

/**
 * @param {string} confidence
 * @returns {string}
 */
export function linkStrengthLabel(confidence) {
  const level = String(confidence || 'low').toUpperCase()
  if (level === 'HIGH') return 'HIGH'
  if (level === 'MEDIUM') return 'MEDIUM'
  return 'LOW'
}

/**
 * @param {string | null | undefined} whyNotHigher
 * @param {object[]} evidence
 * @returns {string | null}
 */
export function explainLimitedConfidence(whyNotHigher, evidence = []) {
  if (whyNotHigher) {
    if (/ip-only/i.test(whyNotHigher)) {
      return 'IP-only relationship. Shared infrastructure may be reused or unrelated.'
    }
    if (/benign noise/i.test(whyNotHigher)) {
      return 'GreyNoise classifies the shared IP as benign noise — treat this link cautiously.'
    }
    if (/no shared hash or domain/i.test(whyNotHigher)) {
      return 'No shared hash or domain indicators — link strength is limited.'
    }
    return whyNotHigher
  }

  const types = new Set(
    evidence
      .filter(ev => ev.type === 'shared_indicator')
      .map(ev => String(ev.ioc_type || '').toUpperCase()),
  )
  if (types.size === 1 && types.has('IP')) {
    return 'IP-only relationship. Shared infrastructure may be reused or unrelated.'
  }
  return null
}

/**
 * @param {object} ev
 * @returns {{ heading: string, lines: string[], source?: string } | null}
 */
export function formatEvidenceItem(ev) {
  if (!ev || typeof ev !== 'object') return null

  if (ev.type === 'shared_indicator') {
    const iocType = String(ev.ioc_type || '').toUpperCase()
    const typeLabel = IOC_TYPE_LABELS[iocType] || iocType || 'Observable'
    const lines = [`Type: ${typeLabel}`]
    const freshness = evidenceFreshnessMeta(ev)
    if (freshness.timeline) {
      lines.push(freshness.timeline)
    }
    if (ev.freshness_reason) {
      lines.push(ev.freshness_reason)
    }
    if (ev.confirmation) {
      const confLabel = CONFIRMATION_LABELS[ev.confirmation] || ev.confirmation
      lines.push(`Confirmation: ${confLabel}`)
    }
    return {
      heading: 'Shared observable',
      value: ev.value || '—',
      lines,
      source: 'AlienVault OTX',
      stale: freshness.stale,
      timeline: freshness.timeline,
      freshnessTitle: freshness.title,
    }
  }

  if (ev.type === 'same_pulse') {
    const rawPulse = ev.pulse_name || ev.pulse_id || ''
    const pulseName = formatIntelLabelText(rawPulse) || rawPulse || 'Unknown pulse'
    return {
      heading: 'Shared OTX pulse',
      value: pulseName,
      lines: ['Both CVEs appear in the same AlienVault OTX pulse.'],
      source: 'AlienVault OTX',
    }
  }

  if (ev.type === 'enrichment_confirmation' && ev.summary) {
    return {
      heading: 'Enrichment confirmation',
      value: ev.summary,
      lines: [],
      source: 'Threat intelligence enrichment',
    }
  }

  return null
}

/**
 * Build analyst-readable connection panel content.
 * @param {object} item — infrastructure correlation row
 * @param {string} cveIdA
 */
export function buildConnectionPanel(item, cveIdA) {
  const evidence = Array.isArray(item?.evidence) ? item.evidence : []
  const formatted = evidence.map(formatEvidenceItem).filter(Boolean)
  const primary = formatted[0]
  const limited = explainLimitedConfidence(item?.why_not_higher, evidence)

  return {
    title: 'WHY BRIEFR LINKED THESE CVEs',
    intro: `BRIEFR linked ${cveIdA} to ${item?.cve_id_b} because their threat intelligence records share observable evidence.`,
    primary,
    additional: formatted.slice(1),
    linkStrength: linkStrengthLabel(item?.confidence),
    limitedConfidence: limited,
    relatedCve: item?.cve_id_b,
    confidenceFactors: confidenceFactorReasons(item?.confidence_factors),
    stale: correlationItemIsStale(item),
    timeline: primary?.timeline || null,
  }
}

/**
 * CORR-PR-5: backend confidence_factors -> ordered, deduped reason strings
 * for the drawer's "why this level" list. Additive -- falls back to nothing
 * (existing limitedConfidence single-sentence caveat still renders) when
 * the backend hasn't sent factors yet.
 * @param {Array<{factor?: string, reason?: string}> | null | undefined} factors
 * @returns {string[]}
 */
export function confidenceFactorReasons(factors) {
  if (!Array.isArray(factors)) return []
  const seen = new Set()
  const reasons = []
  for (const f of factors) {
    const reason = f?.reason
    if (!reason || seen.has(reason)) continue
    seen.add(reason)
    reasons.push(reason)
  }
  return reasons
}

/**
 * @param {object} body — suppression request body
 * @param {string} cveIdA
 * @param {string} [peerCve]
 */
export function suppressionDialogCopy(body, cveIdA, peerCve) {
  const scope = body?.scope
  if (scope === 'infrastructure' || scope === 'cve_pair') {
    const peer = peerCve || body?.key?.cve_id_b || 'another CVE'
    return {
      title: 'MARK CORRELATION AS UNRELATED?',
      body: `BRIEFR linked ${cveIdA} to ${peer} because their threat intelligence records share observable evidence.`,
      note: 'This will suppress this relationship from future correlation results. The CVEs themselves will remain available.',
    }
  }
  if (scope === 'campaign_id') {
    return {
      title: 'MARK CORRELATION AS UNRELATED?',
      body: `BRIEFR linked ${cveIdA} to a campaign correlation.`,
      note: 'This will suppress this campaign link from future correlation results. The CVEs themselves will remain available.',
    }
  }
  return {
    title: 'MARK CORRELATION AS UNRELATED?',
    body: `Suppress this correlation link for ${cveIdA}.`,
    note: 'This will suppress this relationship from future correlation results. The CVEs themselves will remain available.',
  }
}
