import { isValidDomain } from '../../utils/domainValidation.js'
import { IOC_NOT_FOUND_IN_DATABASES } from '../../utils/iocLookupMessages.js'

const IPV4_RE = /^(\d{1,3}\.){3}\d{1,3}$/
const HASH_RE = /^[0-9a-fA-F]{32}$|^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$/

export function extractDomain(val) {
  let v = val.trim()
  if (!v) return ''
  try {
    const bare = v.split('/')[0].split('?')[0].split('#')[0]
    if (v.includes('://') || v.startsWith('//')) {
      const url = v.includes('://') ? v : `https:${v}`
      v = new URL(url).hostname || bare
    } else if (bare.includes(':') && !bare.startsWith('[')) {
      v = new URL(`http://${bare}`).hostname || bare.split(':')[0]
    } else {
      v = bare
    }
  } catch {
    v = v.split('/')[0].split('?')[0].split('#')[0]
    if (v.includes(':') && !v.startsWith('[')) v = v.split(':')[0]
  }
  return v.replace(/\.$/, '').toLowerCase()
}

export function normalizeIocValue(val, type) {
  const v = val.trim()
  if (!v) return v
  if (type === 'domain') return extractDomain(v)
  if (type === 'hash') return v.toLowerCase()
  return v
}

/** Graph IocKind includes `url`; `/api/ioc/lookup` only accepts ip|hash|domain. */
export function lookupCompatibleIoc(value, type) {
  const raw = String(type || '').toLowerCase()
  const text = String(value || '').trim()
  if (raw === 'url' || raw === 'domain') {
    return { type: 'domain', value: normalizeIocValue(text, 'domain') }
  }
  if (raw === 'hash') {
    return { type: 'hash', value: normalizeIocValue(text, 'hash') }
  }
  return { type: 'ip', value: text }
}

export function detectType(val) {
  const v = val.trim()
  if (!v) return null
  if (IPV4_RE.test(v)) return 'ip'
  if (HASH_RE.test(v)) return 'hash'
  const domain = extractDomain(v)
  if (isValidDomain(domain)) return 'domain'
  return null
}

export function verdictInfo(malicious, total) {
  if (!total) return { label: 'unknown', color: 'var(--text3)', pct: 0 }
  const pct = malicious / total
  if (pct < 0.1) return { label: 'clean', color: 'var(--green)', pct }
  if (pct < 0.5) return { label: 'suspicious', color: 'var(--amber)', pct }
  return { label: 'likely malicious', color: 'var(--red)', pct }
}

export function abuseScoreColor(score) {
  if (score == null) return 'var(--text3)'
  if (score >= 75) return 'var(--red)'
  if (score >= 40) return 'var(--amber)'
  return 'var(--green)'
}

export function enginePillClass(category) {
  if (category === 'malicious') return 'malicious'
  if (category === 'suspicious') return 'suspicious'
  if (category === 'harmless') return 'harmless'
  return 'undetected'
}

export function parseError(err) {
  if (err.status === 0) return 'Could not reach the server. Check your connection and try again.'
  if (err.status === 403) return 'Threat-intelligence API key missing or invalid on this server. Ask your administrator.'
  if (err.status === 429) return 'Rate limit reached — try again in 60 seconds'
  if (err.status === 404) return IOC_NOT_FOUND_IN_DATABASES
  if (err.status === 422) return err.message || 'Invalid input — use a full hostname, not a filename or path'
  return err.message || 'Lookup failed — existing session results remain available'
}

export const TYPE_LABELS = {
  ip: 'IP ADDRESS',
  hash: 'FILE HASH',
  domain: 'DOMAIN',
}
