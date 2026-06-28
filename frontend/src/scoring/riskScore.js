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
