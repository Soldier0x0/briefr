/**
 * CVE-aware remediation reference ranking.
 * Hostname alone does not make a vendor advisory.
 */

const VENDOR_HOST_HINTS = [
  'microsoft.com', 'apple.com', 'google.com', 'adobe.com', 'oracle.com',
  'cisco.com', 'vmware.com', 'fortinet.com', 'redhat.com', 'ubuntu.com',
  'debian.org', 'apache.org', 'jenkins.io', 'atlassian.com', 'samsung.com',
]

const NVD_HOSTS = ['nvd.nist.gov', 'nist.gov']
const CISA_HOSTS = ['cisa.gov']

const ADVISORY_PATH_RE = [
  /\/security[-_]?(?:advisory|bulletin)s?\//i,
  /\/security[-_]?(?:advisory|bulletin)/i,
  /\/advisory\//i,
  /\/advisories\//i,
  /\/security\//i,
  /\/vuln(?:erability)?\//i,
  /\/cve-detail\//i,
  /\/cve\//i,
  /kb\d+/i,
]

const DOC_PATH_HINTS = [
  '/docs/', '/documentation/', '/support/', '/learn/', '/products/',
  '/download', '/home', '/index', '/help/',
]

const GITHUB_ADVISORY_RE = /github\.com\/(?:[^/]+\/[^/]+\/security\/advisories|advisories\/)/i

function hostOf(url) {
  try {
    return new URL(url).hostname.toLowerCase()
  } catch {
    return ''
  }
}

function cveIdInUrl(url, cveId) {
  if (!cveId) return false
  return String(url).toUpperCase().includes(String(cveId).toUpperCase())
}

function hasAdvisoryPath(url) {
  return ADVISORY_PATH_RE.some(re => re.test(url))
}

function isVendorHost(host) {
  return VENDOR_HOST_HINTS.some(v => host === v || host.endsWith(`.${v}`))
}

function isNvdHost(host) {
  return NVD_HOSTS.some(n => host.includes(n))
}

function isCisaHost(host) {
  return CISA_HOSTS.some(c => host.includes(c))
}

function isGenericDocUrl(url) {
  const lower = String(url).toLowerCase()
  return DOC_PATH_HINTS.some(h => lower.includes(h))
}

/**
 * Score and label a single reference URL.
 * @returns {{ score: number, label: string }}
 */
export function classifyRemediationReference(url, { cveId, isKev = false } = {}) {
  const lower = String(url || '').toLowerCase()
  const host = hostOf(url)
  if (!host) return { score: -1, label: 'Source reference' }

  const cveSpecific = cveIdInUrl(url, cveId)
  const advisoryPath = hasAdvisoryPath(url)
  const vendor = isVendorHost(host)
  const nvd = isNvdHost(host)
  const cisa = isCisaHost(host)
  const githubAdvisory = GITHUB_ADVISORY_RE.test(url)

  if (vendor && cveSpecific && advisoryPath) {
    return { score: 100, label: 'Vendor advisory' }
  }
  if (cisa && cveSpecific) {
    return { score: 90, label: 'CISA guidance' }
  }
  if (cisa && isKev && lower.includes('known-exploited')) {
    return { score: 88, label: 'CISA guidance' }
  }
  if (vendor && advisoryPath) {
    return { score: 80, label: 'Security advisory' }
  }
  if (githubAdvisory && cveSpecific) {
    return { score: 65, label: 'Security advisory' }
  }
  if (nvd && cveSpecific) {
    return { score: 70, label: 'NVD reference' }
  }
  if (advisoryPath && cveSpecific) {
    return { score: 60, label: 'Security advisory' }
  }
  if (githubAdvisory) {
    return { score: 55, label: 'Security advisory' }
  }
  if (nvd) {
    return { score: 45, label: 'NVD reference' }
  }
  if (vendor && !isGenericDocUrl(url)) {
    return { score: 30, label: 'Vendor reference' }
  }
  if (vendor) {
    return { score: 20, label: 'Vendor reference' }
  }
  if (cveSpecific) {
    return { score: 35, label: 'Source reference' }
  }
  return { score: 10, label: 'Source reference' }
}

/**
 * @param {object} cve
 * @param {string[]} [urls]
 * @returns {{ url: string, label: string, score: number } | null}
 */
export function pickPrimaryRemediationReference(cve, urls = []) {
  const list = Array.isArray(urls) ? urls : (cve?.source_urls || [])
  if (!list.length) return null

  const cveId = cve?.cve_id
  const isKev = !!cve?.is_kev

  const ranked = list
    .map(url => {
      const { score, label } = classifyRemediationReference(url, { cveId, isKev })
      return { url, score, label }
    })
    .filter(r => r.score > 0)
    .sort((a, b) => b.score - a.score)

  if (!ranked.length) return null
  return ranked[0]
}

export function patchStatusLabel(cve) {
  if (cve?.patch_available === true) return 'PATCH AVAILABLE'
  if (cve?.patch_available === false) return 'NO PATCH AVAILABLE'
  return 'PATCH STATUS UNKNOWN'
}
