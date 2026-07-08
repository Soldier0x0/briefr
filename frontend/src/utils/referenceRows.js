/**
 * Semantic reference rows for analyst-readable source links.
 */

import { classifyRemediationReference } from './patchReferences.js'

const HOST_VENDOR_LABELS = {
  'adobe.com': 'Adobe',
  'microsoft.com': 'Microsoft',
  'apple.com': 'Apple',
  'google.com': 'Google',
  'oracle.com': 'Oracle',
  'cisco.com': 'Cisco',
  'vmware.com': 'VMware',
  'fortinet.com': 'Fortinet',
  'redhat.com': 'Red Hat',
  'ubuntu.com': 'Ubuntu',
  'debian.org': 'Debian',
  'apache.org': 'Apache',
  'jenkins.io': 'Jenkins',
  'atlassian.com': 'Atlassian',
  'samsung.com': 'Samsung',
  'nist.gov': 'NVD',
  'nvd.nist.gov': 'NVD',
  'cisa.gov': 'CISA',
  'github.com': 'GitHub',
  'packetstorm.news': 'Packet Storm',
  'packetstormsecurity.com': 'Packet Storm',
  'exploit-db.com': 'Exploit-DB',
  'www.exploit-db.com': 'Exploit-DB',
}

const PATH_TITLE_PATTERNS = [
  { re: /\/security[-_]?(?:advisory|bulletin)s?\/([^/?#]+)/i, transform: slugToTitle },
  { re: /\/advisories?\/([^/?#]+)/i, transform: slugToTitle },
  { re: /\/cve-detail\/([^/?#]+)/i, transform: slugToTitle },
  { re: /\/known-exploited-vulnerabilities-catalog/i, title: 'Known Exploited Vulnerabilities' },
  { re: /\/vuln\/detail\/([^/?#]+)/i, transform: slugToTitle },
]

function slugToTitle(slug) {
  const decoded = decodeURIComponent(String(slug || ''))
    .replace(/[-_]+/g, ' ')
    .replace(/\.(html|htm|php|aspx)$/i, '')
    .trim()
  if (!decoded) return null
  if (/^CVE-\d{4}-\d+$/i.test(decoded)) return decoded.toUpperCase()
  if (/^APSB\d+/i.test(decoded)) return `Security Bulletin ${decoded.toUpperCase()}`
  if (/^KB\d+/i.test(decoded)) return decoded.toUpperCase()
  return decoded.replace(/\b\w/g, c => c.toUpperCase())
}

function hostOf(url) {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^www\./, '')
  } catch {
    return ''
  }
}

function vendorLabelFromHost(host) {
  if (!host) return 'Source'
  if (HOST_VENDOR_LABELS[host]) return HOST_VENDOR_LABELS[host]
  for (const [key, label] of Object.entries(HOST_VENDOR_LABELS)) {
    if (host === key || host.endsWith(`.${key}`)) return label
  }
  const base = host.split('.').slice(-2).join('.')
  const segment = base.split('.')[0]
  if (!segment) return 'Source'
  return segment.charAt(0).toUpperCase() + segment.slice(1)
}

function titleFromUrl(url) {
  try {
    const parsed = new URL(url)
    for (const { re, title, transform } of PATH_TITLE_PATTERNS) {
      const match = parsed.pathname.match(re)
      if (match) {
        if (title) return title
        const derived = transform?.(match[1])
        if (derived) return derived
      }
    }
    const last = parsed.pathname.split('/').filter(Boolean).pop()
    if (last && last.length > 3 && !/^[a-f0-9]{32,}$/i.test(last)) {
      const derived = slugToTitle(last)
      if (derived && derived.length <= 80) return derived
    }
  } catch {
    /* ignore */
  }
  return null
}

/**
 * @param {string} url
 * @param {{ cveId?: string, isKev?: boolean }} [opts]
 * @returns {{ url: string, vendor: string, title: string, kind: string }}
 */
export function buildReferenceRow(url, { cveId, isKev } = {}) {
  const host = hostOf(url)
  const vendor = vendorLabelFromHost(host)
  const derivedTitle = titleFromUrl(url)
  const { label: kind } = classifyRemediationReference(url, { cveId, isKev })

  let title = derivedTitle
  if (!title) {
    if (kind === 'CISA guidance') title = 'Known Exploited Vulnerabilities'
    else if (kind === 'Vendor advisory' || kind === 'Security advisory') title = 'Security advisory'
    else if (kind === 'NVD reference') title = 'Vulnerability detail'
    else title = host || url
  }

  return { url, vendor, title, kind }
}

/**
 * @param {string[]} urls
 * @param {{ cveId?: string, isKev?: boolean }} [opts]
 */
export function buildReferenceRows(urls, opts = {}) {
  const list = Array.isArray(urls) ? urls : []
  const seen = new Set()
  const rows = []
  for (const url of list) {
    if (!url || seen.has(url)) continue
    seen.add(url)
    rows.push(buildReferenceRow(url, opts))
  }
  return rows
}
