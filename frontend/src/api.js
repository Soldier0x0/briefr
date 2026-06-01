const BASE = '/api'

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, options)
  } catch {
    const err = new Error('Network error — is the backend running?')
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

export function fetchStats() {
  return request('/stats')
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
  if (params.search)    qs.set('search', params.search)
  if (params.stack)     qs.set('stack', params.stack)
  if (params.page)      qs.set('page', String(params.page))
  if (params.limit)     qs.set('limit', String(params.limit))
  const query = qs.toString()
  return request(`/cves${query ? `?${query}` : ''}`)
}

export function fetchCVE(cveId) {
  return request(`/cves/${encodeURIComponent(cveId)}`)
}

export function fetchKEVDeadlines(sort = 'recent') {
  return request(`/kev/deadlines?sort=${sort}`)
}

export function fetchUsage() {
  return request('/usage')
}

export function lookupIOC(value, type) {
  return request('/ioc/lookup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value, type }),
  })
}

export function triggerRefresh() {
  return request('/refresh', { method: 'POST' })
}
