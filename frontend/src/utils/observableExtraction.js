/**
 * Staged observable extraction from CVE intelligence text.
 * Stage 1: extract candidates → Stage 2: validate type → Stage 3: classify context → Stage 4: prioritize lookup.
 */

import { DOMAIN_EXTRACT_RE, isValidDomain } from './domainValidation.js'

const IPV4_RE =
  /\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b/g

const IPV6_RE =
  /\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b/g

const SHA256_RE = /\b[a-fA-F0-9]{64}\b/g
const SHA1_RE = /\b[a-fA-F0-9]{40}\b/g
const MD5_RE = /\b[a-fA-F0-9]{32}\b/g

const URL_RE = /\bhttps?:\/\/[^\s<>"')\]]+/gi

/** TLD-like false positives from file extensions in prose or URLs. */
const FALSE_TLD_SUFFIXES = new Set([
  'html', 'htm', 'php', 'asp', 'aspx', 'jsp', 'js', 'css', 'json', 'xml',
  'txt', 'md', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'exe', 'dll',
  'bat', 'sh', 'py', 'rb', 'go', 'java', 'cs', 'ts', 'tsx', 'jsx', 'c', 'h',
  'cpp', 'yml', 'yaml', 'cfg', 'conf', 'ini', 'log', 'sql', 'zip', 'gz',
])

const REFERENCE_DOMAIN_ROOTS = new Set([
  'nist.gov', 'nvd.nist.gov', 'cisa.gov', 'github.com', 'github.io',
  'githubusercontent.com', 'first.org', 'mitre.org', 'attack.mitre.org',
  'atlas.mitre.org', 'greynoise.io', 'virustotal.com', 'abuseipdb.com',
  'otx.alienvault.com', 'alienvault.com', 'projectjupiter.in', 'osv.dev',
  'sploitus.com', 'microsoft.com', 'google.com', 'apple.com', 'oracle.com',
  'adobe.com', 'apache.org', 'ubuntu.com', 'debian.org', 'redhat.com',
  'vmware.com', 'cisco.com', 'fortinet.com', 'wordpress.org', 'mozilla.org',
  'w3.org', 'ietf.org', 'iana.org', 'iana-servers.net', 'example.com',
  'example.org', 'localhost',
])

const ADVISORY_URL_HINTS = [
  'security-advisory', 'security advisory', 'security-bulletin', 'security bulletin',
  '/advisory/', '/security/', '/cve/', 'kb.', 'support.', 'patch',
]

export const OBSERVABLE_CONTEXT = {
  POTENTIAL_IOC: 'potential_ioc',
  SECURITY_ADVISORY: 'security_advisory',
  VENDOR_REFERENCE: 'vendor_reference',
  DOCUMENTATION: 'documentation',
  UNKNOWN: 'unknown',
}

export const OBSERVABLE_TYPES = {
  IPV4: 'ip',
  IPV6: 'ipv6',
  DOMAIN: 'domain',
  URL: 'url',
  SHA256: 'sha256',
  SHA1: 'sha1',
  MD5: 'md5',
}

function normalizeHost(host) {
  return String(host || '').replace(/\.$/, '').toLowerCase()
}

function domainRoot(host) {
  const h = normalizeHost(host)
  const parts = h.split('.')
  if (parts.length < 2) return h
  return parts.slice(-2).join('.')
}

function isReferenceDomain(host) {
  const h = normalizeHost(host)
  if (!h) return true
  if (REFERENCE_DOMAIN_ROOTS.has(h)) return true
  const root = domainRoot(h)
  if (REFERENCE_DOMAIN_ROOTS.has(root)) return true
  return h.endsWith('.gov') || h.endsWith('.mil') || h.endsWith('.edu')
}

function isFalsePositiveDomain(host) {
  const h = normalizeHost(host)
  const tld = h.split('.').pop()
  return FALSE_TLD_SUFFIXES.has(tld)
}

function classifyUrlContext(url) {
  const lower = String(url || '').toLowerCase()
  if (ADVISORY_URL_HINTS.some(h => lower.includes(h))) {
    return OBSERVABLE_CONTEXT.SECURITY_ADVISORY
  }
  try {
    const host = new URL(url).hostname
    if (isReferenceDomain(host)) return OBSERVABLE_CONTEXT.VENDOR_REFERENCE
  } catch {
    // ignore
  }
  return OBSERVABLE_CONTEXT.UNKNOWN
}

function classifyDomainContext(host, sourceText) {
  if (isReferenceDomain(host)) return OBSERVABLE_CONTEXT.VENDOR_REFERENCE
  const lower = normalizeHost(host)
  if (sourceText && ADVISORY_URL_HINTS.some(h => sourceText.toLowerCase().includes(h) && sourceText.toLowerCase().includes(lower))) {
    return OBSERVABLE_CONTEXT.SECURITY_ADVISORY
  }
  return OBSERVABLE_CONTEXT.POTENTIAL_IOC
}

/**
 * Stage 1 — raw candidate extraction from text blobs.
 */
export function extractCandidateObservables(text) {
  const candidates = []
  if (!text) return candidates

  const push = (type, value, source = 'text') => {
    const v = String(value || '').trim()
    if (!v) return
    candidates.push({ type, value: v, source })
  }

  for (const ip of text.match(IPV4_RE) || []) push(OBSERVABLE_TYPES.IPV4, ip)
  for (const ip of text.match(IPV6_RE) || []) push(OBSERVABLE_TYPES.IPV6, ip)
  for (const h of text.match(SHA256_RE) || []) push(OBSERVABLE_TYPES.SHA256, h.toLowerCase())
  for (const h of text.match(SHA1_RE) || []) push(OBSERVABLE_TYPES.SHA1, h.toLowerCase())
  for (const h of text.match(MD5_RE) || []) push(OBSERVABLE_TYPES.MD5, h.toLowerCase())
  for (const url of text.match(URL_RE) || []) push(OBSERVABLE_TYPES.URL, url.replace(/[),.;]+$/, ''))
  for (const d of text.match(DOMAIN_EXTRACT_RE) || []) push(OBSERVABLE_TYPES.DOMAIN, d)

  return candidates
}

/**
 * Stage 2 — validate and normalize observable type.
 */
export function validateObservable(candidate) {
  const { type, value } = candidate
  if (!value) return null

  if (type === OBSERVABLE_TYPES.IPV4) {
    const octets = value.split('.')
    if (octets.length !== 4) return null
    if (!octets.every(o => {
      const n = Number(o)
      return Number.isInteger(n) && n >= 0 && n <= 255
    })) return null
    return { type: OBSERVABLE_TYPES.IPV4, value }
  }

  if (type === OBSERVABLE_TYPES.DOMAIN) {
    const host = normalizeHost(value)
    if (!isValidDomain(host)) return null
    if (isFalsePositiveDomain(host)) return null
    return { type: OBSERVABLE_TYPES.DOMAIN, value: host }
  }

  if (type === OBSERVABLE_TYPES.URL) {
    try {
      const parsed = new URL(value)
      if (!['http:', 'https:'].includes(parsed.protocol)) return null
      return { type: OBSERVABLE_TYPES.URL, value: parsed.href }
    } catch {
      return null
    }
  }

  if ([OBSERVABLE_TYPES.IPV6, OBSERVABLE_TYPES.SHA256, OBSERVABLE_TYPES.SHA1, OBSERVABLE_TYPES.MD5].includes(type)) {
    return { type, value: value.toLowerCase() }
  }

  return null
}

/**
 * Stage 3 — classify context for analyst review.
 */
export function classifyObservableContext(observable, sourceText = '') {
  const { type, value } = observable
  let context = OBSERVABLE_CONTEXT.UNKNOWN

  if (type === OBSERVABLE_TYPES.URL) {
    context = classifyUrlContext(value)
  } else if (type === OBSERVABLE_TYPES.DOMAIN) {
    context = classifyDomainContext(value, sourceText)
  } else if ([OBSERVABLE_TYPES.IPV4, OBSERVABLE_TYPES.IPV6].includes(type)) {
    context = OBSERVABLE_CONTEXT.POTENTIAL_IOC
  } else if ([OBSERVABLE_TYPES.SHA256, OBSERVABLE_TYPES.SHA1, OBSERVABLE_TYPES.MD5].includes(type)) {
    context = OBSERVABLE_CONTEXT.POTENTIAL_IOC
  }

  return { ...observable, context }
}

const LOOKUP_PRIORITY = {
  [OBSERVABLE_CONTEXT.POTENTIAL_IOC]: 0,
  [OBSERVABLE_CONTEXT.UNKNOWN]: 1,
  [OBSERVABLE_CONTEXT.SECURITY_ADVISORY]: 2,
  [OBSERVABLE_CONTEXT.DOCUMENTATION]: 3,
  [OBSERVABLE_CONTEXT.VENDOR_REFERENCE]: 4,
}

/**
 * Stage 4 — prioritize observables suitable for threat-intel lookup.
 */
export function prioritizeObservablesForLookup(classified, max = 5) {
  const seen = new Set()
  const sorted = [...classified].sort(
    (a, b) => (LOOKUP_PRIORITY[a.context] ?? 9) - (LOOKUP_PRIORITY[b.context] ?? 9),
  )

  const out = []
  for (const item of sorted) {
    if (item.context === OBSERVABLE_CONTEXT.VENDOR_REFERENCE) continue
    if (item.context === OBSERVABLE_CONTEXT.DOCUMENTATION) continue

    const key = `${item.type}:${item.value}`
    if (seen.has(key)) continue
    seen.add(key)

    const lookupType = item.type === OBSERVABLE_TYPES.IPV6 ? 'ip'
      : item.type === OBSERVABLE_TYPES.URL ? 'url'
        : item.type === OBSERVABLE_TYPES.SHA256 ? 'sha256'
          : item.type === OBSERVABLE_TYPES.SHA1 ? 'sha1'
            : item.type === OBSERVABLE_TYPES.MD5 ? 'md5'
              : item.type

    out.push({
      type: lookupType,
      value: item.value,
      context: item.context,
    })
    if (out.length >= max) break
  }
  return out
}

/**
 * Full pipeline for CVE observable extraction.
 * @returns {{ type: string, value: string, context?: string }[]}
 */
export function extractObservablesFromCve(cve, max = 5) {
  const scans = Array.isArray(cve?.greynoise_scans) ? cve.greynoise_scans : []
  const classified = []

  for (const scan of scans) {
    if (!scan?.ip) continue
    const validated = validateObservable({ type: OBSERVABLE_TYPES.IPV4, value: scan.ip })
    if (validated) {
      classified.push(classifyObservableContext({ ...validated, source: 'greynoise' }))
    }
  }

  const sourceText = [
    cve?.description,
    cve?.summary,
    ...(Array.isArray(cve?.source_urls) ? cve.source_urls : []),
  ]
    .filter(Boolean)
    .join(' ')

  if (sourceText) {
    const candidates = extractCandidateObservables(sourceText)
    for (const cand of candidates) {
      const validated = validateObservable(cand)
      if (!validated) continue
      classified.push(classifyObservableContext(validated, sourceText))
    }
  }

  return prioritizeObservablesForLookup(classified, max)
}
