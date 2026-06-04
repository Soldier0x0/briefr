/**
 * BRIEFR Risk Score v1.1a — mirrors backend/scoring/risk.py (no momentum).
 */

import { getSavedStack } from './cveFilters.js'

export const WEIGHTS = {
  asset: 0.37,
  kev: 0.26,
  epss: 0.16,
  exploit: 0.11,
  cvss: 0.10,
}

const DEFAULT_ASSET_UNKNOWN = 0.5

function parseDate(value) {
  if (!value) return null
  const text = String(value).trim()
  if (text.length >= 10 && text[4] === '-' && text[7] === '-') {
    const d = new Date(text.slice(0, 10) + 'T00:00:00Z')
    if (!Number.isNaN(d.getTime())) return d
  }
  const d = new Date(text)
  return Number.isNaN(d.getTime()) ? null : d
}

function daysSince(value) {
  const d = parseDate(value)
  if (!d) return null
  const now = new Date()
  return Math.floor((now - d) / 86400000)
}

function assetTokens(userAssets) {
  if (!userAssets?.length) return []
  const tokens = []
  for (const item of userAssets) {
    if (typeof item === 'string') {
      const t = item.trim()
      if (t) tokens.push(t.toLowerCase())
    } else if (item && typeof item === 'object') {
      for (const key of ['product', 'vendor', 'name', 'stack']) {
        const v = (item[key] || '').trim()
        if (v) tokens.push(v.toLowerCase())
      }
    }
  }
  return tokens
}

function assetComponentScore(cve, userAssets) {
  const tokens = assetTokens(userAssets)
  if (!tokens.length) return DEFAULT_ASSET_UNKNOWN

  const products = (cve.affected_products || []).map(p => String(p).toLowerCase())
  const blob = [
    ...products,
    cve.description || '',
    cve.summary || '',
  ].join(' ').toLowerCase()

  let best = 0
  for (const token of tokens) {
    for (const product of products) {
      if (product.includes(token) || token.includes(product)) {
        const vendor = product.split(':')[0]?.trim().toLowerCase()
        if (vendor && (token === vendor || product.startsWith(token + ':'))) {
          best = Math.max(best, 0.85)
        } else {
          best = Math.max(best, 1.0)
        }
      }
    }
    if (blob.includes(token)) best = Math.max(best, 0.55)
    for (const product of products) {
      const vendor = product.split(':')[0]?.trim().toLowerCase()
      if (vendor && (token.includes(vendor) || vendor.includes(token))) {
        best = Math.max(best, 0.75)
      }
    }
  }
  return Math.min(1, best)
}

function kevComponentScore(isKev, dateAdded, dueDate) {
  if (!isKev) return 0
  let score = 0.82
  const addedDays = daysSince(dateAdded)
  if (addedDays != null) {
    if (addedDays <= 7) score += 0.18
    else if (addedDays <= 30) score += 0.12
    else if (addedDays <= 90) score += 0.06
    else score += 0.02
  }
  const due = parseDate(dueDate)
  if (due) {
    const daysUntil = Math.ceil((due - new Date()) / 86400000)
    if (daysUntil < 0) score = Math.min(1, score + 0.12)
    else if (daysUntil <= 14) score = Math.min(1, score + 0.08)
    else if (daysUntil <= 30) score = Math.min(1, score + 0.04)
  }
  return Math.min(1, score)
}

function exploitTier(exploits, hasPoc) {
  if (!exploits?.length && !hasPoc) return 0
  const types = (exploits || []).map(e => (e.type || '').toLowerCase())
  const blob = (exploits || [])
    .map(e => `${e.title || ''} ${e.source || ''} ${e.url || ''}`)
    .join(' ')
    .toLowerCase()
  if (types.includes('metasploit') || blob.includes('metasploit')) return 1.0
  if (types.some(t => t === 'weaponised' || t === 'weaponized')) return 0.88
  if (['metasploit', 'weaponized', 'weaponised', 'in-the-wild'].some(h => blob.includes(h))) {
    return 0.85
  }
  if (types.includes('poc')) return 0.55
  if (hasPoc) return 0.35
  return 0
}

function epssComponentScore(epss) {
  if (epss == null || epss < 0) return 0.25
  return Math.max(0, Math.min(1, epss))
}

function cvssComponentScore(cvss, severity) {
  if (cvss != null) return Math.max(0, Math.min(1, cvss / 10))
  const sev = (severity || '').toUpperCase()
  if (sev === 'CRITICAL') return 0.95
  if (sev === 'HIGH') return 0.75
  if (sev === 'MEDIUM') return 0.45
  if (sev === 'LOW') return 0.2
  return 0.15
}

function componentSentences(cve, userAssets, components) {
  const asset = components.asset
  let assetText
  if (!userAssets?.length) {
    assetText = 'Asset exposure is unknown — no profile loaded; using neutral weighting.'
  } else if (asset >= 0.85) {
    assetText = 'Strong match to assets in your profile; prioritize for your environment.'
  } else if (asset >= 0.55) {
    assetText = 'Partial overlap with your asset profile; review affected products.'
  } else {
    assetText = 'Low overlap with your stated assets; lower priority unless internet-facing.'
  }

  const kev = components.kev
  const kevText =
    kev <= 0
      ? 'Not on CISA KEV; no confirmed federal catalogue exploitation signal.'
      : kev >= 0.95
        ? 'CISA KEV with recent catalogue activity; treat as immediate priority.'
        : 'Listed on CISA KEV; elevated priority with recency-weighted urgency.'

  const epssVal = cve.epss_score
  const epssText =
    epssVal != null
      ? `EPSS ${(epssVal * 100).toFixed(1)}% contributes ${(components.epss * 100).toFixed(0)}% normalized likelihood to the score.`
      : 'EPSS data missing; neutral exploit-likelihood weight applied.'

  const exploit = components.exploit
  let exploitText
  if (exploit >= 0.95) exploitText = 'Public Metasploit or weaponised tooling sharply increases practical risk.'
  else if (exploit >= 0.5) exploitText = 'Proof-of-concept or weaponised references raise attacker accessibility.'
  else if (exploit > 0) exploitText = 'Limited public exploit material; moderate uplift to score.'
  else exploitText = 'No public exploits identified; exploit component does not add uplift.'

  const cvssVal = cve.cvss_score
  const sev = cve.severity || 'unknown'
  const cvssText =
    cvssVal != null
      ? `CVSS ${cvssVal} (${sev}) maps to ${(components.cvss * 100).toFixed(0)}% of the technical severity band.`
      : `Severity ${sev} used where CVSS is unavailable.`

  return { asset: assetText, kev: kevText, epss: epssText, exploit: exploitText, cvss: cvssText }
}

export function exploitsFromCveFields(cve) {
  const exploits = []
  const urls = cve.source_urls || []
  for (const url of urls) {
    const lower = (url || '').toLowerCase()
    if (lower.includes('metasploit')) exploits.push({ type: 'metasploit', url })
    else if (['weaponized', 'weaponised', 'in-the-wild'].some(h => lower.includes(h))) {
      exploits.push({ type: 'weaponised', url })
    }
  }
  if (cve.public_exploits?.length) {
    for (const ex of cve.public_exploits) exploits.push(ex)
  }
  if (cve.has_poc && !exploits.length) exploits.push({ type: 'poc' })
  return exploits
}

/** User asset profile from saved stack (v1 session placeholder until full profile UI). */
export function getUserAssetProfile() {
  const stack = getSavedStack()
  if (!stack) return null
  return stack.split(/[,\n]+/).map(s => s.trim()).filter(Boolean)
}

export function calculateRiskScore(cve, userAssets = null, exploits = null) {
  const assets = userAssets?.length ? userAssets : null
  const exploitList = exploits ?? exploitsFromCveFields(cve)

  const components = {
    asset: assetComponentScore(cve, assets),
    kev: kevComponentScore(cve.is_kev, cve.kev_date_added, cve.kev_due_date),
    epss: epssComponentScore(cve.epss_score),
    exploit: exploitTier(exploitList, cve.has_poc),
    cvss: cvssComponentScore(cve.cvss_score, cve.severity),
  }

  if (!assets) components.asset = DEFAULT_ASSET_UNKNOWN

  const weighted =
    components.asset * WEIGHTS.asset +
    components.kev * WEIGHTS.kev +
    components.epss * WEIGHTS.epss +
    components.exploit * WEIGHTS.exploit +
    components.cvss * WEIGHTS.cvss

  const score = Math.round(Math.max(0, Math.min(100, weighted * 100)) * 10) / 10

  const labels = {
    asset: 'Asset exposure',
    kev: 'CISA KEV',
    epss: 'EPSS likelihood',
    exploit: 'Public exploits',
    cvss: 'CVSS severity',
  }

  const sentences = componentSentences(cve, assets, components)
  const breakdown = Object.keys(WEIGHTS).map(id => ({
    id,
    label: labels[id],
    weight: WEIGHTS[id],
    value: Math.round(components[id] * 10000) / 10000,
    points: Math.round(components[id] * WEIGHTS[id] * 1000) / 10,
    sentence: sentences[id],
  }))

  return { score, components, breakdown }
}

export function riskScoreColor(score) {
  if (score == null || Number.isNaN(score)) return 'var(--text3)'
  if (score >= 90) return 'var(--red)'
  if (score >= 70) return 'color-mix(in srgb, var(--red) 70%, transparent)'
  if (score >= 40) return 'var(--amber)'
  return 'var(--text3)'
}
