/**
 * Select the most relevant official remediation reference for a CVE.
 * Priority: vendor advisory → CISA KEV action → NVD → project security advisory.
 */

const VENDOR_HOST_HINTS = [
  'microsoft.com', 'apple.com', 'google.com', 'adobe.com', 'oracle.com',
  'cisco.com', 'vmware.com', 'fortinet.com', 'redhat.com', 'ubuntu.com',
  'debian.org', 'apache.org', 'jenkins.io', 'atlassian.com', 'samsung.com',
]

const NVD_HOSTS = ['nvd.nist.gov', 'nist.gov']

const CISA_HOSTS = ['cisa.gov']

const PROJECT_SECURITY_HINTS = [
  '/security/', '/advisory/', 'security-advisory', 'security bulletin',
  'github.com', 'gitlab.com',
]

function hostOf(url) {
  try {
    return new URL(url).hostname.toLowerCase()
  } catch {
    return ''
  }
}

function scoreReference(url, { isKev }) {
  const lower = String(url || '').toLowerCase()
  const host = hostOf(url)
  if (!host) return -1

  if (VENDOR_HOST_HINTS.some(v => host === v || host.endsWith(`.${v}`))) return 100
  if (CISA_HOSTS.some(c => host.includes(c)) && isKev) return 90
  if (NVD_HOSTS.some(n => host.includes(n))) return 70
  if (PROJECT_SECURITY_HINTS.some(h => lower.includes(h))) return 60
  if (isKev && lower.includes('cisa')) return 85
  return 10
}

/**
 * @param {object} cve
 * @param {string[]} [urls]
 * @returns {{ url: string, label: string } | null}
 */
export function pickPrimaryRemediationReference(cve, urls = []) {
  const list = Array.isArray(urls) ? urls : (cve?.source_urls || [])
  if (!list.length) return null

  const ranked = list
    .map(url => ({ url, score: scoreReference(url, { isKev: !!cve?.is_kev }) }))
    .filter(r => r.score > 0)
    .sort((a, b) => b.score - a.score)

  if (!ranked.length) return null

  const best = ranked[0]
  const host = hostOf(best.url)
  let label = 'Official reference'
  if (VENDOR_HOST_HINTS.some(v => host.includes(v))) label = 'Vendor advisory'
  else if (CISA_HOSTS.some(c => host.includes(c))) label = 'CISA guidance'
  else if (NVD_HOSTS.some(n => host.includes(n))) label = 'NVD reference'
  else if (PROJECT_SECURITY_HINTS.some(h => best.url.toLowerCase().includes(h))) {
    label = 'Security advisory'
  }

  return { url: best.url, label }
}

export function patchStatusLabel(cve) {
  if (cve?.patch_available === true) return 'PATCH AVAILABLE'
  if (cve?.patch_available === false) return 'NO PATCH AVAILABLE'
  return 'PATCH STATUS UNKNOWN'
}
