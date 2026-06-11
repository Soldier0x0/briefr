const BASE = '/api'
const REQUEST_TIMEOUT_MS = 20000

async function request(path, options = {}) {
  // Bounded failure: a hung backend must not leave spinners forever.
  if (!options.signal && typeof AbortSignal?.timeout === 'function') {
    options = { ...options, signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) }
  }
  let res
  try {
    res = await fetch(`${BASE}${path}`, options)
  } catch (e) {
    const timedOut = e?.name === 'TimeoutError'
    const err = new Error(
      timedOut
        ? 'Request timed out — the backend may be overloaded.'
        : 'Network error — is the backend running?',
    )
    err.status = 0
    throw err
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    const err = new Error(body.detail || `HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return res.json()
}

export function fetchStats({ frameworks = [] } = {}) {
  const qs = new URLSearchParams()
  const fw = Array.isArray(frameworks) ? frameworks.filter(Boolean) : []
  if (fw.length) qs.set('frameworks', fw.join(','))
  const query = qs.toString()
  return request(`/stats${query ? `?${query}` : ''}`)
}

export function fetchStatsTimeline(days = 90) {
  return request(`/stats/timeline?days=${days}`)
}

export function fetchHealth(tz = 'UTC') {
  const qs = new URLSearchParams({ tz })
  return request(`/health?${qs}`)
}

export function fetchCVEs(params = {}) {
  const qs = new URLSearchParams()
  if (params.severity)  qs.set('severity', params.severity)
  if (params.kev_only)  qs.set('kev_only', 'true')
  if (params.poc_only)  qs.set('poc_only', 'true')
  if (params.epss_min != null) qs.set('epss_min', String(params.epss_min))
  if (params.search)    qs.set('search', params.search)
  if (params.stack)     qs.set('stack', params.stack)
  if (params.vendors)   qs.set('vendors', params.vendors)
  if (params.technique) qs.set('technique', params.technique)
  if (params.published_on) qs.set('published_on', params.published_on)
  if (params.summary_only) qs.set('summary_only', 'true')
  if (params.ai_context_only) qs.set('ai_context_only', 'true')
  if (params.frameworks) qs.set('frameworks', params.frameworks)
  if (params.page)      qs.set('page', String(params.page))
  if (params.limit)     qs.set('limit', String(params.limit))
  const query = qs.toString()
  return request(`/cves${query ? `?${query}` : ''}`)
}

export function fetchCVE(cveId) {
  return request(`/cves/${encodeURIComponent(cveId)}`)
}

/** Asset profile CPE match — sole API endpoint that receives asset inventory. */
export function fetchCveAssetMatch(assets) {
  return request('/cves/match', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assets }),
  })
}

export function fetchCVESentences(cveId) {
  return request(`/cves/${encodeURIComponent(cveId)}/sentences`)
}

export function fetchCVEEpssHistory(cveId) {
  return request(`/cves/${encodeURIComponent(cveId)}/epss-history`)
}

export function fetchCVERelated(cveId, limit = 5) {
  return request(`/cves/${encodeURIComponent(cveId)}/related?limit=${limit}`)
}

export function fetchCVECorrelation(cveId, sector = '') {
  const qs = sector ? `?sector=${encodeURIComponent(sector)}` : ''
  return request(`/cves/${encodeURIComponent(cveId)}/correlation${qs}`)
}

export function fetchCVEDetection(cveId, product = '') {
  const qs = product ? `?product=${encodeURIComponent(product)}` : ''
  return request(`/cves/${encodeURIComponent(cveId)}/detection${qs}`)
}

export function fetchCVEMomentum(cveId) {
  return request(`/cves/${encodeURIComponent(cveId)}/momentum`)
}

export function fetchCVEsForExport(params = {}) {
  const qs = new URLSearchParams()
  if (params.severity)  qs.set('severity', params.severity)
  if (params.kev_only)  qs.set('kev_only', 'true')
  if (params.poc_only)  qs.set('poc_only', 'true')
  if (params.epss_min != null) qs.set('epss_min', String(params.epss_min))
  if (params.search)    qs.set('search', params.search)
  if (params.stack)     qs.set('stack', params.stack)
  if (params.vendors)   qs.set('vendors', params.vendors)
  if (params.technique) qs.set('technique', params.technique)
  if (params.published_on) qs.set('published_on', params.published_on)
  if (params.summary_only) qs.set('summary_only', 'true')
  if (params.ai_context_only) qs.set('ai_context_only', 'true')
  if (params.frameworks) qs.set('frameworks', params.frameworks)
  qs.set('max_rows', '500')
  const query = qs.toString()
  return request(`/cves/export${query ? `?${query}` : ''}`)
}

export function fetchTopTechniques(limit = 10) {
  return request(`/techniques/top?limit=${limit}`)
}

export function fetchAtlasTechniques() {
  return request('/atlas/techniques')
}

export function fetchAtlasCaseStudies(limit = 50) {
  return request(`/atlas/casestudies?limit=${limit}`)
}

export function fetchIncidentNews() {
  return request('/case-studies/news')
}

/** Combined RSS + ATLAS cards for Incidents tab (single round-trip). */
export function fetchCaseStudyFeed(atlasLimit = 80) {
  return request(`/case-studies/feed?atlas_limit=${atlasLimit}`)
}

export function fetchKEVDeadlines(sort = 'recent') {
  return request(`/kev/deadlines?sort=${sort}`)
}

export function fetchUsage() {
  return request('/usage')
}

export function fetchIOCUsage() {
  return request('/usage/ioc')
}

export function lookupIOC(value, type, options = {}) {
  return request('/ioc/lookup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      value,
      type,
      greynoise: Boolean(options.greynoise),
    }),
  })
}

export function fetchOTXPulseIocs(pulseId, limit = 10) {
  return request(`/otx/pulses/${encodeURIComponent(pulseId)}/iocs?limit=${limit}`)
}

/** AI executive summary — only call when analyst exports a PDF. */
export function fetchAiSummary({
  cves = [],
  iocs = [],
  actors = [],
  investigationDuration = 1,
}) {
  return request('/ai/summary', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      cves,
      iocs,
      actors,
      investigation_duration: investigationDuration,
    }),
  })
}
