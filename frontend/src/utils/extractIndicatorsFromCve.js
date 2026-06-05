/**
 * Pull analyst-reviewable IOC candidates from a CVE record (no auto-lookup).
 */

import { DOMAIN_EXTRACT_RE, isValidDomain } from './domainValidation.js'

const DOMAIN_BLOCKLIST = new Set([
  'nist.gov',
  'nvd.nist.gov',
  'cisa.gov',
  'github.com',
  'github.io',
  'githubusercontent.com',
  'first.org',
  'mitre.org',
  'attack.mitre.org',
  'atlas.mitre.org',
  'greynoise.io',
  'virustotal.com',
  'abuseipdb.com',
  'projectjupiter.in',
  'osv.dev',
  'sploitus.com',
])

const IPV4_RE =
  /\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b/g

function domainBlocked(host) {
  const h = host.toLowerCase()
  if (DOMAIN_BLOCKLIST.has(h)) return true
  const parts = h.split('.')
  if (parts.length >= 2) {
    const root = parts.slice(-2).join('.')
    if (DOMAIN_BLOCKLIST.has(root)) return true
  }
  return h.endsWith('.gov') || h.endsWith('.mil')
}

/**
 * @param {object} cve
 * @param {number} [max=5]
 * @returns {{ type: 'ip'|'domain', value: string }[]}
 */
export function extractIndicatorsFromCve(cve, max = 5) {
  const seen = new Set()
  const out = []

  function push(type, raw) {
    if (out.length >= max) return false
    const value = String(raw || '').trim()
    if (!value) return true
    const key = `${type}:${type === 'domain' ? value.toLowerCase() : value}`
    if (seen.has(key)) return true
    if (type === 'domain' && domainBlocked(value.toLowerCase())) return true
    seen.add(key)
    out.push({ type, value: type === 'domain' ? value.toLowerCase() : value })
    return out.length < max
  }

  const scans = Array.isArray(cve?.greynoise_scans) ? cve.greynoise_scans : []
  for (const scan of scans) {
    if (scan?.ip && !push('ip', scan.ip)) break
  }

  const text = [
    cve?.description,
    cve?.summary,
    ...(Array.isArray(cve?.source_urls) ? cve.source_urls : []),
  ]
    .filter(Boolean)
    .join(' ')

  if (text) {
    const ips = text.match(IPV4_RE) || []
    for (const ip of ips) {
      if (!push('ip', ip)) break
    }
    const domains = text.match(DOMAIN_EXTRACT_RE) || []
    for (const d of domains) {
      if (!isValidDomain(d)) continue
      if (!push('domain', d)) break
    }
  }

  return out
}
