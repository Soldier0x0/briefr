/**
 * BRIEFR Risk Score v1.1b
 * 6 components — momentum now active (v1.1b weights).
 *
 * calculateRiskScore(cve, assetProfile, backendMatchScore, momentumScore)
 * Momentum is fetched lazily from /api/cves/{id}/momentum on drawer open.
 * For card renders, momentumScore defaults to 0 (no API call per card).
 *
 * Weights are fetched once at startup from GET /api/config/risk and cached
 * in _weights. The hardcoded values below are the fallback used when the
 * fetch fails or has not yet completed.
 */

import { fetchRiskWeights } from '../api.js'

const DEFAULT_ASSET_UNKNOWN = 0.5

// v1.1b fallback constants — kept in sync with backend/scoring/risk.py.
// fetchAndCacheRiskWeights() overwrites this at startup from /api/config/risk.
let _weights = {
  asset:    0.35,
  kev:      0.25,
  epss:     0.15,
  exploit:  0.10,
  cvss:     0.10,
  momentum: 0.05,
}

/**
 * Fetch v1.1b weights from GET /api/config/risk and update the module cache.
 * Silently ignored on failure — the hardcoded fallback remains active.
 * Call once at app startup (fire-and-forget).
 *
 * Validation rules (all must pass, otherwise fallback is kept):
 *  1. Response has a `weights` object.
 *  2. Received object contains exactly the expected keys — no more, no fewer.
 *  3. Every value is a finite number.
 *  4. Values sum to 1.0 (tolerance 1e-6).
 * On success _weights is replaced wholesale, not merged, to avoid partial-key
 * corruption (e.g. a single-key response with sum == 1.0 would otherwise
 * produce a total weight of 1.65 via spread).
 */
export function getRiskWeights() {
  return { ..._weights }
}

export async function fetchAndCacheRiskWeights() {
  try {
    const data = await fetchRiskWeights()
    if (data && data.weights && typeof data.weights === 'object') {
      const w = data.weights
      const expectedKeys = Object.keys(_weights)
      const receivedKeys = Object.keys(w)
      const keysMatch =
        receivedKeys.length === expectedKeys.length &&
        expectedKeys.every(k => Object.prototype.hasOwnProperty.call(w, k))
      const allFinite = expectedKeys.every(k => typeof w[k] === 'number' && Number.isFinite(w[k]))
      if (keysMatch && allFinite) {
        const total = expectedKeys.reduce((s, k) => s + w[k], 0)
        if (Math.abs(total - 1.0) < 1e-6) {
          _weights = w
        }
      }
    }
  } catch {
    // network error or backend unavailable — fallback constants stay active
  }
}

function num(value, fallback = 0) {
  if (value == null || value === '') return fallback
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function boolish(value) {
  return value === true || value === 1 || value === '1' || value === 'true'
}


// ── Date helpers ─────────────────────────────────────────

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
  return Math.max(0, Math.floor((Date.now() - d.getTime()) / 86400000))
}

// ── Asset Match (graduation table) ───────────────────────
//
// Tier  Score  Condition
// 1     1.00   vendor:cpeProduct match AND version matches
// 2     0.90   vendor:cpeProduct match, no version or version mismatch
// 3     0.80   OS product name found in affected_products
// 4     0.75   cpeProduct alone matches (no vendor match)
// 5     0.65   vendor alone matches
// 6     0.55   AI system name in affected_products
// 7     0.45   display name or cpeProduct in CVE description/summary
// 8     0.35   AI system name in CVE description/summary
// 9     0.00   profile loaded, nothing matches

function assetMatchInfo(cve, assetProfile) {
  if (!assetProfile) {
    return { score: DEFAULT_ASSET_UNKNOWN, matchType: null }
  }

  const affected = (cve.affected_products || []).map(p => String(p).toLowerCase())
  const descBlob = `${cve.description || ''} ${cve.summary || ''}`.toLowerCase()

  const apps = assetProfile.applications || []
  const oses = assetProfile.operatingSystems || []
  const ais = assetProfile.aiSystems || []

  let bestScore = 0
  let bestTier = 'no match'
  let bestLabel = null

  // Check applications
  for (const app of apps) {
    const vendor = (app.vendor || '').toLowerCase().trim()
    const cpeProduct = (app.cpeProduct || '').toLowerCase().trim()
    const displayName = (app.product || '').trim()
    const version = (app.version || '').trim()

    for (const prod of affected) {
      const parts = prod.split(':')
      const affVendor = (parts[0] || '').trim()
      const affProduct = (parts[1] || '').trim()

      const vendorMatch =
        vendor && (vendor === affVendor || affVendor.includes(vendor) || vendor.includes(affVendor))
      const productMatch =
        cpeProduct && (cpeProduct === affProduct || affProduct.includes(cpeProduct) || cpeProduct.includes(affProduct))

      if (vendorMatch && productMatch) {
        if (version && version.length > 0) {
          // Tier 1: exact CPE match — version present and product+vendor matches
          if (bestScore < 1.0) {
            bestScore = 1.0
            bestTier = 'exact CPE match'
            bestLabel = `${displayName} ${version}`
          }
        } else {
          // Tier 2: CPE product match without version
          if (bestScore < 0.9) {
            bestScore = 0.9
            bestTier = 'CPE product match'
            bestLabel = displayName || cpeProduct
          }
        }
      } else if (productMatch && !vendorMatch) {
        // Tier 4: product alone matches
        if (bestScore < 0.75) {
          bestScore = 0.75
          bestTier = 'product match'
          bestLabel = displayName || cpeProduct
        }
      } else if (vendorMatch && !productMatch) {
        // Tier 5: vendor-only match
        if (bestScore < 0.65) {
          bestScore = 0.65
          bestTier = 'vendor match'
          bestLabel = vendor
        }
      }
    }

    // Tier 7: fuzzy description match
    if (bestScore < 0.45) {
      const needle = displayName.toLowerCase()
      if ((needle && descBlob.includes(needle)) || (cpeProduct && descBlob.includes(cpeProduct))) {
        bestScore = 0.45
        bestTier = 'description mention'
        bestLabel = displayName || cpeProduct
      }
    }
  }

  // Check operating systems
  for (const os of oses) {
    const osProd = (os.product || '').toLowerCase().trim()
    const osVersion = (os.version || '').trim()
    const osDisplay = (os.product || '').trim()

    for (const prod of affected) {
      const affProduct = (prod.split(':')[1] || prod).trim()
      if (osProd && (affProduct.includes(osProd) || osProd.includes(affProduct) || prod.includes(osProd))) {
        // Tier 3: OS product found
        if (bestScore < 0.8) {
          bestScore = 0.8
          bestTier = 'OS match'
          bestLabel = osDisplay + (osVersion ? ` ${osVersion}` : '')
        }
      }
    }

    // OS name in description
    if (bestScore < 0.45 && osProd && descBlob.includes(osProd)) {
      bestScore = 0.45
      bestTier = 'description mention'
      bestLabel = osDisplay
    }
  }

  // Check AI systems
  for (const ai of ais) {
    const aiName = (typeof ai === 'string' ? ai : ai?.product || '').trim()
    if (!aiName) continue
    const aiLower = aiName.toLowerCase()

    for (const prod of affected) {
      const affProduct = (prod.split(':')[1] || prod).trim()
      if (aiLower && (affProduct.includes(aiLower) || aiLower.includes(affProduct) || prod.includes(aiLower))) {
        // Tier 6: AI system in affected products
        if (bestScore < 0.55) {
          bestScore = 0.55
          bestTier = 'AI system match'
          bestLabel = aiName
        }
      }
    }

    // Tier 8: AI name in description
    if (bestScore < 0.35 && aiLower && descBlob.includes(aiLower)) {
      bestScore = 0.35
      bestTier = 'AI system reference'
      bestLabel = aiName
    }
  }

  // Build human-readable match type string
  let matchType
  switch (bestTier) {
    case 'exact CPE match':
      matchType = `${bestLabel} directly affected (exact CPE match)`
      break
    case 'CPE product match':
      matchType = `${bestLabel} found in affected products (CPE product match)`
      break
    case 'product match':
      matchType = `${bestLabel} found in affected products (product match)`
      break
    case 'vendor match':
      matchType = `${bestLabel} vendor matched in affected products`
      break
    case 'OS match':
      matchType = `${bestLabel} found in affected products (OS match)`
      break
    case 'AI system match':
      matchType = `${bestLabel} AI/ML system in affected products`
      break
    case 'AI system reference':
      matchType = `${bestLabel} referenced in vulnerability description`
      break
    case 'description mention':
      matchType = `${bestLabel} mentioned in vulnerability description`
      break
    default:
      matchType = 'No matching assets in your profile'
  }

  return { score: bestScore, matchType }
}

export function calculateAssetMatch(cve, assetProfile) {
  return assetMatchInfo(cve, assetProfile).score
}

export function getAssetMatchType(cve, assetProfile) {
  if (!assetProfile) return null
  return assetMatchInfo(cve, assetProfile).matchType
}

// ── KEV Score with recency weighting ─────────────────────

export function calculateKevScore(cve) {
  if (!boolish(cve?.is_kev)) return 0

  const addedDays = daysSince(cve.kev_date_added)

  if (addedDays == null) return 0.84
  if (addedDays <= 7) return 1.0
  if (addedDays <= 30) return 0.94
  if (addedDays <= 90) return 0.88
  return 0.84
}

// ── Exploit Score (Metasploit / weaponised / PoC graduation) ─

export function calculateExploitScore(cve) {
  const exploits = (cve.public_exploits || []).filter(Boolean)
  const types = exploits.map(e => (e.type || '').toLowerCase())

  const urlBlob = [
    ...(cve.source_urls || []),
    ...exploits.map(e => `${e.title || ''} ${e.source || ''} ${e.url || ''}`),
  ]
    .join(' ')
    .toLowerCase()

  if (types.includes('metasploit') || urlBlob.includes('metasploit')) return 1.0

  if (
    types.some(t => t === 'weaponised' || t === 'weaponized') ||
    ['weaponized', 'weaponised', 'in-the-wild'].some(h => urlBlob.includes(h))
  )
    return 0.88

  if (types.includes('poc')) return 0.55

  if (cve.has_poc || exploits.length > 0) return 0.35

  return 0
}

// ── Component sentences ───────────────────────────────────

function buildSentences(cve, assetProfile, scores, assetMatchType) {
  // Asset sentence
  let assetSentence
  if (!assetProfile) {
    assetSentence = 'Load an asset profile for personalised scoring'
  } else if (assetMatchType && assetMatchType !== 'No matching assets in your profile') {
    assetSentence = assetMatchType
  } else {
    assetSentence = 'No matching assets found in your profile'
  }

  // KEV sentence
  let kevSentence
  if (!boolish(cve?.is_kev)) {
    kevSentence = 'Not listed in CISA Known Exploited Vulnerabilities catalogue'
  } else {
    const addedDays = daysSince(cve.kev_date_added)
    if (addedDays == null) {
      kevSentence = 'Listed in CISA Known Exploited Vulnerabilities catalogue'
    } else if (addedDays === 0) {
      kevSentence = 'Added to CISA KEV today — immediate priority'
    } else if (addedDays === 1) {
      kevSentence = 'Added to CISA KEV yesterday'
    } else if (addedDays <= 7) {
      kevSentence = `Added to CISA KEV ${addedDays} days ago`
    } else if (addedDays <= 30) {
      kevSentence = `Added to CISA KEV ${addedDays} days ago`
    } else {
      const weeks = Math.floor(addedDays / 7)
      kevSentence =
        weeks === 1
          ? 'Listed in CISA KEV for over a week'
          : `Listed in CISA KEV for ${weeks} weeks`
    }
  }

  // EPSS sentence
  const epssVal = num(cve.epss_score, null)
  const epssSentence =
    epssVal != null
      ? `${(epssVal * 100).toFixed(1)}% exploitation probability`
      : 'No EPSS data available for this CVE'

  // Exploit sentence
  let exploitSentence
  const exploitScore = scores.exploit
  if (exploitScore >= 1.0) {
    exploitSentence = 'Metasploit module available — actively weaponised'
  } else if (exploitScore >= 0.88) {
    const exploits = cve.public_exploits || []
    const src = exploits.find(e => e.source)?.source || null
    exploitSentence = src
      ? `Weaponised exploit on ${src}`
      : 'Weaponised exploit available in public sources'
  } else if (exploitScore >= 0.55) {
    exploitSentence = 'Public proof-of-concept exploit available'
  } else if (exploitScore > 0) {
    exploitSentence = 'Exploit references found in public sources'
  } else {
    exploitSentence = 'No public exploits identified'
  }

  // CVSS sentence
  const cvssVal = num(cve.cvss_score, null)
  const cvssSentence =
    cvssVal != null
      ? `${cvssVal.toFixed(1)} / 10.0`
      : `Severity: ${cve.severity || 'unknown'}`

  return {
    asset: assetSentence,
    kev: kevSentence,
    epss: epssSentence,
    exploit: exploitSentence,
    cvss: cvssSentence,
  }
}

function assetScoreFromBackend(matchScore) {
  const score = num(matchScore, 0)
  if (score >= 100) {
    return {
      score: 1,
      matchType: 'Your asset directly affected (exact CPE version match)',
    }
  }
  if (score >= 55) {
    return {
      score: 0.55,
      matchType: 'Your asset found in affected products (CPE product match)',
    }
  }
  if (score > 0) {
    return {
      score: score / 100,
      matchType: 'Partial match to your asset profile',
    }
  }
  return { score: 0, matchType: 'No matching assets in your profile' }
}

// ── Main scoring function ─────────────────────────────────

export function calculateRiskScore(
  cve,
  assetProfile,
  backendMatchScore = null,
  momentumScore = 0,
) {
  if (!cve) return null

  let assetScore
  let assetMatchType
  if (assetProfile) {
    const backend = assetScoreFromBackend(backendMatchScore ?? 0)
    assetScore = backend.score
    assetMatchType = backend.matchType
    if (backend.score === 0) {
      const client = assetMatchInfo(cve, assetProfile)
      if (client.score > assetScore) {
        assetScore = client.score
        assetMatchType = client.matchType
      }
    }
  } else {
    ({ score: assetScore, matchType: assetMatchType } = assetMatchInfo(cve, assetProfile))
  }

  const kevScore    = calculateKevScore(cve)
  const epssScore   = num(cve.epss_score, 0)
  const exploitScore = calculateExploitScore(cve)
  const cvssScore   = num(cve.cvss_score, 0) / 10
  const momScore    = Math.min(1, Math.max(0, num(momentumScore, 0)))

  const w = _weights
  const raw =
    assetScore   * w.asset +
    kevScore     * w.kev +
    epssScore    * w.epss +
    exploitScore * w.exploit +
    cvssScore    * w.cvss +
    momScore     * w.momentum

  const total = Math.round(raw * 100 * 10) / 10

  const scores = {
    asset: assetScore, kev: kevScore, epss: epssScore,
    exploit: exploitScore, cvss: cvssScore, momentum: momScore,
  }
  const sentences = buildSentences(cve, assetProfile, scores, assetMatchType)

  return {
    total,
    components: {
      asset: {
        score: assetScore,
        weight: w.asset,
        points: Math.round(assetScore * w.asset * 100 * 10) / 10,
        sentence: sentences.asset,
      },
      kev: {
        score: kevScore,
        weight: w.kev,
        points: Math.round(kevScore * w.kev * 100 * 10) / 10,
        sentence: sentences.kev,
      },
      epss: {
        score: epssScore,
        weight: w.epss,
        points: Math.round(epssScore * w.epss * 100 * 10) / 10,
        sentence: sentences.epss,
      },
      exploit: {
        score: exploitScore,
        weight: w.exploit,
        points: Math.round(exploitScore * w.exploit * 100 * 10) / 10,
        sentence: sentences.exploit,
      },
      cvss: {
        score: cvssScore,
        weight: w.cvss,
        points: Math.round(cvssScore * w.cvss * 100 * 10) / 10,
        sentence: sentences.cvss,
      },
      momentum: {
        score: momScore,
        weight: w.momentum,
        points: Math.round(momScore * w.momentum * 100 * 10) / 10,
        sentence: momScore > 0
          ? `Threat momentum active — score raised by active signals`
          : 'No recent threat momentum signals detected',
      },
    },
    assetMatchType,
    hasProfile: assetProfile != null,
    momentumScore: momScore,
  }
}


// ── Hero summary (drawer collapsed state) ─────────────────

const EXPLOIT_SUMMARY_PARTS = [
  { min: 1.0, text: 'Metasploit module' },
  { min: 0.88, text: 'Weaponised exploit' },
  { min: 0.55, text: 'Public PoC' },
  { min: 0.01, text: 'Exploit refs' },
]

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

// ── Colour helpers ────────────────────────────────────────

/**
 * Colour for the overall risk score (card + drawer header).
 * Thresholds: 0-39 text3, 40-69 amber, 70-89 dark-red, 90-100 red.
 */
export function riskScoreColor(score) {
  if (score == null || Number.isNaN(score)) return 'var(--text3)'
  if (score >= 90) return 'var(--red)'
  if (score >= 70) return '#b84a28'
  if (score >= 40) return 'var(--amber)'
  return 'var(--text3)'
}

/**
 * Colour for individual component progress bars.
 * High (≥0.7) → red, medium (≥0.3) → amber, low → text3.
 */
export function componentBarColor(score) {
  if (score >= 0.7) return 'var(--red)'
  if (score >= 0.3) return 'var(--amber)'
  return 'var(--text3)'
}
