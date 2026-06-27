/** Instance-aware share/deep links (self-hosted or hosted). */

export function appOrigin() {
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin.replace(/\/$/, '')
  }
  const fromEnv = import.meta.env.VITE_PUBLIC_URL
  if (fromEnv) return String(fromEnv).replace(/\/$/, '')
  return ''
}

export function cveDeepLink(cveId) {
  const id = (cveId || '').trim().toUpperCase()
  if (!id) return ''
  const origin = appOrigin()
  const path = `/?cve=${encodeURIComponent(id)}`
  return origin ? `${origin}${path}` : path
}

export function nvdCveLink(cveId) {
  const id = (cveId || '').trim().toUpperCase()
  if (!id) return ''
  return `https://nvd.nist.gov/vuln/detail/${id}`
}

export function buildCveShareText(cve, { linkType = 'briefr' } = {}) {
  const id = cve?.cve_id || ''
  const desc = (cve?.description || '').slice(0, 60).trimEnd()
  const url = linkType === 'nvd' ? nvdCveLink(id) : cveDeepLink(id)
  const via = linkType === 'nvd' ? 'NVD' : 'BRIEFR'
  return `${id} — ${desc}\nvia ${via}: ${url}`
}
