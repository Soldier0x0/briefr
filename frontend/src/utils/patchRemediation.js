/**
 * Remediation section semantics — separates vendor fix from CISA required action.
 */

import {
  classifyRemediationReference,
  patchStatusLabel,
  pickPrimaryRemediationReference,
} from './patchReferences.js'

/**
 * Build vendor remediation content for the REMEDIATION block.
 * Uses concise analyst copy — not the combined patch+KEV paragraph.
 *
 * @param {{ cve?: object, sentences?: object }} input
 * @returns {{ status: string, text: string, isGeneric: boolean } | null}
 */
export function buildVendorRemediationDisplay({ cve, sentences } = {}) {
  if (!cve) return null

  const status = patchStatusLabel(cve)
  const patchText = (sentences?.patch || '').trim()
  const kevAction = (
    sentences?.kev_required_action ||
    cve?.kev_required_action ||
    ''
  ).trim()

  if (status === 'PATCH AVAILABLE') {
    return {
      status,
      text: 'Vendor fix available.',
      isGeneric: false,
    }
  }

  if (status === 'NO PATCH AVAILABLE') {
    return {
      status,
      text: 'No official vendor patch is currently available.',
      isGeneric: false,
    }
  }

  if (patchText && !textOverlaps(patchText, kevAction)) {
    return {
      status,
      text: patchText,
      isGeneric: true,
    }
  }

  return {
    status,
    text: 'Vendor remediation guidance unavailable — monitor vendor advisories.',
    isGeneric: true,
  }
}

function textOverlaps(a, b) {
  if (!a || !b) return false
  const normA = a.toLowerCase().slice(0, 80)
  const normB = b.toLowerCase().slice(0, 80)
  return normA.includes(normB.slice(0, 40)) || normB.includes(normA.slice(0, 40))
}

/**
 * Highest-ranked vendor advisory reference (excludes CISA/NVD when possible).
 */
export function pickVendorRemediationReference(cve, urls = []) {
  const list = Array.isArray(urls) ? urls : (cve?.source_urls || [])
  const cveId = cve?.cve_id
  const ranked = list
    .map(url => {
      const { score, label } = classifyRemediationReference(url, { cveId, isKev: !!cve?.is_kev })
      const host = (() => {
        try { return new URL(url).hostname.toLowerCase() } catch { return '' }
      })()
      const isCisa = host.includes('cisa.gov')
      const isNvd = host.includes('nist.gov')
      const adjusted = isCisa ? score - 50 : isNvd ? score - 20 : score
      return { url, score: adjusted, label }
    })
    .filter(r => r.score > 0)
    .sort((a, b) => b.score - a.score)

  if (ranked.length) {
    const top = ranked[0]
    return { url: top.url, label: top.label === 'Vendor reference' ? 'vendor security advisory' : top.label.toLowerCase() }
  }
  return pickPrimaryRemediationReference(cve, list)
}

/**
 * CISA guidance reference when KEV or CISA host present.
 */
export function pickCisaRemediationReference(cve, urls = []) {
  const list = Array.isArray(urls) ? urls : (cve?.source_urls || [])
  const cveId = cve?.cve_id
  const cisa = list
    .map(url => {
      const { score, label } = classifyRemediationReference(url, { cveId, isKev: true })
      const host = (() => {
        try { return new URL(url).hostname.toLowerCase() } catch { return '' }
      })()
      if (!host.includes('cisa.gov')) return null
      return { url, score, label }
    })
    .filter(Boolean)
    .sort((a, b) => b.score - a.score)

  if (cisa.length) {
    return { url: cisa[0].url, label: 'CISA guidance' }
  }

  if (cve?.is_kev) {
    return {
      url: 'https://www.cisa.gov/known-exploited-vulnerabilities-catalog',
      label: 'CISA guidance',
    }
  }
  return null
}

/**
 * Build CISA remediation content for the REMEDIATION block.
 * Never uses sentences.kev (catalogue status only).
 *
 * @param {{ cve?: object, sentences?: object }} input
 * @returns {{ tag: string, text: string, variant: string } | null}
 */
export function buildKevRemediationDisplay({ cve, sentences } = {}) {
  const requiredAction = (
    sentences?.kev_required_action ||
    cve?.kev_required_action ||
    ''
  ).trim()

  if (requiredAction) {
    return {
      tag: 'CISA REQUIRED ACTION',
      text: requiredAction,
      variant: 'required-action',
    }
  }

  if (cve?.is_kev) {
    return {
      tag: 'CISA KEV LISTED',
      text:
        'Remediate according to vendor instructions and applicable CISA KEV requirements.',
      variant: 'kev-listed',
    }
  }

  return null
}

/**
 * KEV status sentences describe catalogue membership — not mitigation guidance.
 */
export function isKevStatusMitigationLabel(label) {
  const normalized = String(label || '').trim().toUpperCase()
  return normalized === 'CISA MITIGATION GUIDANCE'
}
