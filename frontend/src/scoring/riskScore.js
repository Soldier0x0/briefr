/**
 * BRIEFR Risk Score UI helpers.
 *
 * Canonical scoring runs on the backend: POST /api/cves/{cve_id}/risk
 * Weights for formula display come from GET /api/config/risk (cached at startup).
 */

import { fetchRiskWeights } from '../api.js'

const DEFAULT_WEIGHTS = {
  asset: 0.35,
  kev: 0.25,
  epss: 0.15,
  exploit: 0.10,
  cvss: 0.10,
  momentum: 0.05,
}

let _weights = { ...DEFAULT_WEIGHTS }

export function getRiskWeights() {
  return { ..._weights }
}

export async function fetchAndCacheRiskWeights() {
  try {
    const data = await fetchRiskWeights()
    if (data?.weights && typeof data.weights === 'object') {
      const w = data.weights
      const expectedKeys = Object.keys(DEFAULT_WEIGHTS)
      const receivedKeys = Object.keys(w)
      const keysMatch =
        receivedKeys.length === expectedKeys.length &&
        expectedKeys.every(k => Object.prototype.hasOwnProperty.call(w, k))
      const allFinite = expectedKeys.every(
        k => typeof w[k] === 'number' && Number.isFinite(w[k]),
      )
      if (keysMatch && allFinite) {
        const total = expectedKeys.reduce((s, k) => s + w[k], 0)
        if (Math.abs(total - 1.0) < 1e-6) {
          _weights = w
        }
      }
    }
  } catch {
    // keep bundled fallback
  }
}

const EXPLOIT_SUMMARY_PARTS = [
  { min: 1.0, text: 'Metasploit module' },
  { min: 0.88, text: 'Weaponised exploit' },
  { min: 0.55, text: 'Public PoC' },
  { min: 0.01, text: 'Exploit refs' },
]

function boolish(value) {
  return value === true || value === 1 || value === '1' || value === 'true'
}

export function buildRiskHeroSummary(cve, riskScore) {
  if (!cve || !riskScore) return ''

  const parts = []
  const { hasProfile, assetMatchType, components } = riskScore

  if (hasProfile) {
    if (assetMatchType && assetMatchType !== 'No matching assets in your profile') {
      parts.push('Matches your stack')
    } else {
      parts.push('No stack match')
    }
  }

  if (boolish(cve?.is_kev)) parts.push('KEV listed')

  const exploitScore = components?.exploit?.score ?? 0
  for (const tier of EXPLOIT_SUMMARY_PARTS) {
    if (exploitScore >= tier.min) {
      parts.push(tier.text)
      break
    }
  }

  if (cve.cvss_score != null) {
    parts.push(`CVSS ${cve.cvss_score.toFixed(1)}`)
  } else if (cve.severity && cve.severity !== 'UNKNOWN') {
    parts.push(cve.severity)
  }

  if (!parts.length && components?.epss?.score > 0) {
    parts.push(`${(components.epss.score * 100).toFixed(1)}% EPSS`)
  }

  return parts.slice(0, 3).join(' · ')
}

export const RISK_COMPONENT_LABELS = {
  asset: 'Asset Match',
  kev: 'KEV Status',
  epss: 'EPSS',
  exploit: 'Exploit Avail',
  cvss: 'CVSS',
  momentum: 'Momentum',
}

/** Analyst-facing asset exposure tiers (UI only — scoring unchanged). */
export const ASSET_EXPOSURE_TIERS = {
  NOT_LOADED: 'NOT_LOADED',
  STRONG: 'STRONG',
  HIGH: 'HIGH',
  POSSIBLE: 'POSSIBLE',
  NO_MATCH: 'NO_MATCH',
  UNKNOWN: 'UNKNOWN',
}

/** Backend CPE matcher label — version range evaluated in matching/cpe.py */
const BACKEND_EXACT_CPE_VERSION =
  'Your asset directly affected (exact CPE version match)'

const BACKEND_CPE_PRODUCT =
  'Your asset found in affected products (CPE product match)'

/**
 * Map backend assetMatchType to analyst-safe wording.
 * Fuzzy matcher scores can reach 1.0 without vulnerable-version proof.
 */
export function inferAssetMatchSemantics(assetMatchType, assetScore) {
  const mt = String(assetMatchType || '').trim()

  if (!mt || mt === 'No matching assets in your profile' || assetScore === 0) {
    return {
      tier: ASSET_EXPOSURE_TIERS.NO_MATCH,
      label: 'NO MATCH FOUND',
      headline: 'NO PROFILE MATCH DETECTED',
      detail:
        'No products, vendors, operating systems, or technologies in your asset profile match this CVE\'s affected products.',
    }
  }

  if (mt === BACKEND_EXACT_CPE_VERSION) {
    return {
      tier: ASSET_EXPOSURE_TIERS.STRONG,
      label: 'STRONG MATCH',
      headline: 'HIGH ASSET RELEVANCE',
      detail:
        `${mt} — CPE version evaluated against stored vulnerable version constraints.`,
    }
  }

  if (mt === BACKEND_CPE_PRODUCT) {
    return {
      tier: ASSET_EXPOSURE_TIERS.HIGH,
      label: 'HIGH ASSET RELEVANCE',
      headline: 'PRODUCT OVERLAP DETECTED',
      detail: `${mt} — product-level CPE overlap; exact vulnerable version not confirmed.`,
    }
  }

  if (mt.includes('directly affected (exact CPE match)')) {
    return {
      tier: ASSET_EXPOSURE_TIERS.HIGH,
      label: 'HIGH ASSET RELEVANCE',
      headline: 'PRODUCT/VERSION OVERLAP',
      detail:
        `${mt} — profile product/vendor overlap; vulnerable version range not verified by CPE constraints.`,
    }
  }

  if (
    mt.includes('(CPE product match)')
    || mt.includes('(OS match)')
    || assetScore >= 0.8
  ) {
    return {
      tier: ASSET_EXPOSURE_TIERS.HIGH,
      label: 'HIGH ASSET RELEVANCE',
      headline: 'STACK OVERLAP DETECTED',
      detail: mt,
    }
  }

  if (
    mt.includes('mentioned in vulnerability description')
    || mt.includes('referenced in vulnerability description')
    || mt.includes('description mention')
    || mt.includes('referenced in')
  ) {
    return {
      tier: ASSET_EXPOSURE_TIERS.POSSIBLE,
      label: 'POSSIBLE MATCH',
      headline: 'WEAK TEXTUAL OVERLAP',
      detail: `${mt} — mention in CVE text or partial profile overlap only.`,
    }
  }

  if (
    mt.includes('product match')
    || mt.includes('vendor match')
    || mt.includes('AI system match')
    || (assetScore >= 0.35 && assetScore < 0.8)
  ) {
    return {
      tier: ASSET_EXPOSURE_TIERS.POSSIBLE,
      label: 'POSSIBLE MATCH',
      headline: 'PARTIAL STACK OVERLAP',
      detail: mt,
    }
  }

  return {
    tier: ASSET_EXPOSURE_TIERS.UNKNOWN,
    label: 'UNKNOWN',
    headline: 'MATCH STATUS UNCLEAR',
    detail: mt || 'Unable to determine asset relevance from available profile and CVE data.',
  }
}

/**
 * Classify asset exposure for display. Backend uses DEFAULT_ASSET_UNKNOWN (0.5)
 * when profile is null — documented here, not changed in the formula.
 */
export function getAssetExposureStatus(riskScore) {
  if (!riskScore) return null

  const { hasProfile, assetMatchType, components } = riskScore
  const assetScore = components?.asset?.score ?? 0
  const assetPoints = components?.asset?.points ?? 0
  const weight = components?.asset?.weight ?? getRiskWeights().asset

  if (!hasProfile) {
    return {
      tier: ASSET_EXPOSURE_TIERS.NOT_LOADED,
      label: 'ASSET DATA NOT LOADED',
      headline: 'EXPOSURE UNKNOWN',
      detail:
        'Load an asset profile to determine whether this CVE affects your environment.',
      matchReason: null,
      showSignalBar: false,
      formulaNote: `Formula placeholder: 0.500 × ${(weight * 100).toFixed(0)}% × 100 = ${assetPoints.toFixed(1)} pts (neutral scoring input — not exposure probability)`,
    }
  }

  const semantics = inferAssetMatchSemantics(assetMatchType, assetScore)

  return {
    tier: semantics.tier,
    label: semantics.label,
    headline: semantics.headline,
    detail: semantics.detail,
    matchReason: assetMatchType && semantics.tier !== ASSET_EXPOSURE_TIERS.NO_MATCH
      ? assetMatchType
      : null,
    showSignalBar: semantics.tier !== ASSET_EXPOSURE_TIERS.NO_MATCH,
    signalScore: assetScore,
    formulaNote: null,
  }
}

/** Operational Priority + Threat surface (ADR-002). */
export const THREAT_WEIGHTS = {
  kev: 0.25 / 0.65,
  epss: 0.15 / 0.65,
  exploit: 0.10 / 0.65,
  cvss: 0.10 / 0.65,
  momentum: 0.05 / 0.65,
}

export const KEV_FLOOR = 80

export const THREAT_COMPONENT_LABELS = {
  kev: 'KEV Status',
  epss: 'EPSS',
  exploit: 'Exploit Avail',
  cvss: 'CVSS',
  momentum: 'Momentum',
}

export const ENV_TIER_LABELS = {
  CONFIRMED: 'CONFIRMED MATCH',
  LIKELY: 'LIKELY OVERLAP',
  POSSIBLE: 'POSSIBLE OVERLAP',
  WEAK: 'WEAK OVERLAP',
  NO_MATCH: 'NO MATCH',
  UNKNOWN: 'ENV UNKNOWN',
}

export const OP_BAND_LABELS = {
  P1: 'P1 — ACT NOW',
  P2: 'P2 — INVESTIGATE',
  P3: 'P3 — SCHEDULE',
  P4: 'P4 — INFORMATIONAL',
}

function num(value, fallback = 0) {
  if (value == null || value === '') return fallback
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function daysSince(value) {
  if (!value) return null
  const text = String(value).trim().slice(0, 10)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return null
  const d = new Date(`${text}T00:00:00Z`)
  const now = new Date()
  return Math.floor((now - d) / 86400000)
}

function kevScoreRaw(cve) {
  if (!boolish(cve?.is_kev)) return 0
  const addedDays = daysSince(cve?.kev_date_added)
  if (addedDays == null) return 0.84
  if (addedDays <= 7) return 1.0
  if (addedDays <= 30) return 0.94
  if (addedDays <= 90) return 0.88
  return 0.84
}

function exploitScoreRaw(cve) {
  const exploits = (cve?.public_exploits || []).filter(Boolean)
  const types = exploits.map(e => String(e?.type || '').toLowerCase())
  const urlBlob = [
    ...(cve?.source_urls || []),
    ...exploits.map(e => `${e?.title || ''} ${e?.source || ''} ${e?.url || ''}`),
  ].join(' ').toLowerCase()
  if (types.includes('metasploit') || urlBlob.includes('metasploit')) return 1.0
  if (
    types.some(t => t === 'weaponised' || t === 'weaponized')
    || ['weaponized', 'weaponised', 'in-the-wild'].some(h => urlBlob.includes(h))
  ) return 0.88
  if (types.includes('poc')) return 0.55
  if (cve?.has_poc || exploits.length) return 0.35
  return 0.0
}

export function threatBand(score) {
  if (score >= 80) return 'CRIT'
  if (score >= 60) return 'HIGH'
  if (score >= 40) return 'MED'
  return 'LOW'
}

export function calculateThreatScore(cve, momentumScore = 0) {
  if (!cve) return null
  const rawScores = {
    kev: kevScoreRaw(cve),
    epss: num(cve.epss_score, 0),
    exploit: exploitScoreRaw(cve),
    cvss: num(cve.cvss_score, 0) / 10,
    momentum: Math.min(1, Math.max(0, num(momentumScore, 0))),
  }
  let additive = Object.entries(rawScores).reduce(
    (sum, [k, raw]) => sum + raw * THREAT_WEIGHTS[k],
    0,
  ) * 100
  additive = Math.round(additive * 10) / 10
  let kevFloorApplied = false
  let score = additive
  if (boolish(cve.is_kev)) {
    score = Math.max(additive, KEV_FLOOR)
    kevFloorApplied = score > additive
  }
  score = Math.round(score * 10) / 10
  const components = {}
  for (const [key, raw] of Object.entries(rawScores)) {
    const w = THREAT_WEIGHTS[key]
    components[key] = {
      raw,
      weight: w,
      points: Math.round(raw * w * 100 * 10) / 10,
    }
  }
  return {
    version: 'threat-1.0',
    score,
    band: threatBand(score),
    components,
    kev_floor_applied: kevFloorApplied,
    additive_score: additive,
  }
}

export function classifyEnvironment(cve, profile, backendMatchScore = null) {
  if (!profile) {
    return {
      version: 'environment-1.0',
      tier: 'UNKNOWN',
      score: null,
      version_verified: false,
      evidence_label: 'No asset profile loaded',
    }
  }
  const backendScore = Number(backendMatchScore || 0)
  if (backendScore >= 100) {
    return {
      version: 'environment-1.0',
      tier: 'CONFIRMED',
      score: 1.0,
      version_verified: true,
      evidence_label: BACKEND_EXACT_CPE_VERSION,
    }
  }
  if (backendScore === 0) {
    return {
      version: 'environment-1.0',
      tier: 'NO_MATCH',
      score: 0,
      version_verified: false,
      evidence_label: 'No matching assets in your profile',
    }
  }
  if (backendScore >= 55) {
    return {
      version: 'environment-1.0',
      tier: 'LIKELY',
      score: backendScore / 100,
      version_verified: false,
      evidence_label: BACKEND_CPE_PRODUCT,
    }
  }
  void cve
  return {
    version: 'environment-1.0',
    tier: 'WEAK',
    score: backendScore / 100,
    version_verified: false,
    evidence_label: 'Partial match to your asset profile',
  }
}

export function correlationEscalation(correlationResult) {
  const campaigns = correlationResult?.campaigns || []
  for (const camp of campaigns) {
    const lifecycle = String(camp.lifecycle || '').toLowerCase()
    if (!['active', 'emerging'].includes(lifecycle)) continue
    if (String(camp.confidence || '').toLowerCase() !== 'high') continue
    if ((camp.member_count || 0) < 2) continue
    const evidence = camp.evidence || []
    const hasSamePulse = evidence.some(e => e.type === 'same_pulse')
    const hasStrongIoc = evidence.some(
      e => e.type === 'shared_indicator'
        && ['HASH', 'DOMAIN'].includes(String(e.ioc_type || '').toUpperCase()),
    )
    if (hasSamePulse && hasStrongIoc) return true
  }
  return false
}

const OP_BASE_TABLE = {
  CRIT: { CONFIRMED: 'P1', LIKELY: 'P1', POSSIBLE: 'P2', WEAK: 'P2', UNKNOWN: 'P1', NO_MATCH: 'P3' },
  HIGH: { CONFIRMED: 'P1', LIKELY: 'P2', POSSIBLE: 'P2', WEAK: 'P2', UNKNOWN: 'P2', NO_MATCH: 'P3' },
  MED: { CONFIRMED: 'P2', LIKELY: 'P2', POSSIBLE: 'P3', WEAK: 'P3', UNKNOWN: 'P3', NO_MATCH: 'P4' },
  LOW: { CONFIRMED: 'P3', LIKELY: 'P3', POSSIBLE: 'P4', WEAK: 'P4', UNKNOWN: 'P4', NO_MATCH: 'P4' },
}

export function deriveOperationalPriority(threatBandName, envTier, corrEscalation = false) {
  const base = OP_BASE_TABLE[threatBandName]?.[envTier]
    ?? OP_BASE_TABLE.LOW?.[envTier]
    ?? 'P4'
  let band = base
  const provisional = envTier === 'UNKNOWN'
  let escalated = false
  if (corrEscalation && (band === 'P2' || band === 'P3')) {
    band = band === 'P2' ? 'P1' : 'P2'
    escalated = band !== base
  }
  return {
    version: 'operational-priority-1.0',
    band,
    provisional,
    escalated_by_correlation: escalated,
    base_band: base,
  }
}

/** Exploit / momentum raw for sections still reading legacy component shape. */
export function threatComponentRaw(riskScore, key) {
  return riskScore?.threat?.components?.[key]?.raw
    ?? riskScore?.legacy_risk_v11b?.components?.[key]?.score
    ?? 0
}

export function getEnvironmentDisplay(riskScore) {
  const env = riskScore?.environment
  if (!env) return null
  return {
    tier: env.tier,
    label: ENV_TIER_LABELS[env.tier] || env.tier,
    evidence: env.evidence_label,
    versionVerified: env.version_verified,
  }
}

export function getOperationalPriorityDisplay(riskScore) {
  const op = riskScore?.operational_priority
  if (!op) return null
  return {
    band: op.band,
    label: OP_BAND_LABELS[op.band] || op.band,
    provisional: op.provisional,
    escalated: op.escalated_by_correlation,
    rationale: op.rationale,
  }
}

export function buildOperationalHeroSummary(cve, riskScore) {
  if (!cve || !riskScore?.threat) return ''
  const parts = []
  const op = riskScore.operational_priority
  if (op?.provisional) parts.push('Provisional')
  if (op?.escalated_by_correlation) parts.push('Campaign escalated')
  if (boolish(cve?.is_kev)) parts.push('KEV listed')
  const exploitRaw = threatComponentRaw(riskScore, 'exploit')
  for (const tier of EXPLOIT_SUMMARY_PARTS) {
    if (exploitRaw >= tier.min) {
      parts.push(tier.text)
      break
    }
  }
  if (cve.cvss_score != null) parts.push(`CVSS ${Number(cve.cvss_score).toFixed(1)}`)
  return parts.slice(0, 3).join(' · ')
}

export function operationalBandColor(band) {
  if (band === 'P1') return 'var(--red)'
  if (band === 'P2') return '#b84a28'
  if (band === 'P3') return 'var(--amber)'
  return 'var(--text3)'
}

export function environmentTierColor(tier) {
  if (tier === 'CONFIRMED') return 'var(--red)'
  if (tier === 'LIKELY') return 'var(--amber)'
  if (tier === 'POSSIBLE' || tier === 'WEAK') return 'var(--accent)'
  if (tier === 'NO_MATCH') return 'var(--text3)'
  return 'var(--text3)'
}

export function riskScoreColor(score) {
  if (score == null || Number.isNaN(score)) return 'var(--text3)'
  if (score >= 90) return 'var(--red)'
  if (score >= 70) return '#b84a28'
  if (score >= 40) return 'var(--amber)'
  return 'var(--text3)'
}

/** Score color with severity fallback so medium/high CVEs are not flat grey. */
export function riskScoreDisplayColor(score, severity) {
  const byScore = riskScoreColor(score)
  if (byScore !== 'var(--text3)') return byScore
  const sev = String(severity || '').toUpperCase()
  if (sev === 'CRITICAL') return 'var(--red)'
  if (sev === 'HIGH') return 'var(--amber)'
  if (sev === 'MEDIUM') return 'var(--accent)'
  return byScore
}

export function componentBarColor(score) {
  if (score >= 0.7) return 'var(--red)'
  if (score >= 0.3) return 'var(--amber)'
  return 'var(--text3)'
}
