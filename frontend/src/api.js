import { outboundJobsPath } from './apiOutboundJobs.js'

const BASE = '/api'
const REQUEST_TIMEOUT_MS = 20000

// Shared in-flight refresh promise so concurrent 401s share one
// /api/auth/refresh call instead of each racing to rotate the same refresh
// token — a second independent call would find the token already rotated
// and trip the backend's reuse-detection, revoking every session.
let refreshPromise = null

function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'include' })
      .then(res => res.ok)
      .catch(() => false)
      .finally(() => { refreshPromise = null })
  }
  return refreshPromise
}

async function doFetch(path, options) {
  if (!options.signal && typeof AbortSignal?.timeout === 'function') {
    options = { ...options, signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) }
  }
  options = { credentials: 'include', ...options }
  try {
    return await fetch(`${BASE}${path}`, options)
  } catch (e) {
    if (e?.name === 'AbortError') {
      throw e
    }
    const timedOut = e?.name === 'TimeoutError'
    const err = new Error(
      timedOut
        ? 'Request timed out — the server may be overloaded. Try again in a moment.'
        : 'Could not reach the server. Check your connection and try again.',
    )
    err.status = 0
    throw err
  }
}

async function request(path, options = {}, _retried = false) {
  // Bounded failure: a hung backend must not leave spinners forever.
  const res = await doFetch(path, options)

  if (!res.ok) {
    const isRefreshExempt = path === '/auth/login' || path === '/auth/refresh' || path === '/auth/setup'
    if (res.status === 401 && !isRefreshExempt) {
      if (!_retried && (await refreshAccessToken())) {
        return request(path, options, true)
      }
      window.dispatchEvent(new CustomEvent('briefr-auth-expired'))
    }
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    const err = new Error(body.detail || `HTTP ${res.status}`)
    err.status = res.status
    err.requestId = res.headers?.get?.('X-Request-ID') || ''
    throw err
  }
  return res.json()
}

// ── Built-in app login (decision 2026-06-11) ───────────────────────────────

export function login(username, password, rememberMe = false) {
  return request('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, remember_me: rememberMe }),
  })
}

export function fetchSetupRequired() {
  return request('/auth/setup-required')
}

export function setupAccount(username, password) {
  return request('/auth/setup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
}

export function logout() {
  return request('/auth/logout', { method: 'POST' })
}

export function fetchMe() {
  return request('/auth/me')
}

export function fetchUserStack() {
  return request('/me/stack')
}

/** Q3 CPE software catalog typeahead (requires ≥3 chars). */
export function suggestStackCatalog(query, { limit = 20, category } = {}) {
  const qs = new URLSearchParams()
  qs.set('q', query || '')
  if (limit) qs.set('limit', String(limit))
  if (category) qs.set('category', category)
  return request(`/stack/catalog/suggest?${qs.toString()}`)
}

/** Q4 Tier A stack coverage + backfill. */
export function fetchStackCoverage() {
  return request('/stack/coverage')
}

export function agreeStackBackfill() {
  return request('/stack/backfill/agree', { method: 'POST' })
}

export function fetchStackBackfillRun(runId) {
  return request(`/stack/backfill/${runId}`)
}

export function resumeStackBackfill(runId) {
  return request(`/stack/backfill/${runId}/resume`, { method: 'POST' })
}

export function saveUserStack(body) {
  return request('/me/stack', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function fetchUserPreferences() {
  return request('/me/preferences')
}

export function patchUserPreferences(body) {
  return request('/me/preferences', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function fetchSessions() {
  return request('/auth/sessions')
}

export function revokeSession(sessionId) {
  return request(`/auth/sessions/${sessionId}`, { method: 'DELETE' })
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
  if (params.kev_overdue_only) qs.set('kev_overdue_only', 'true')
  if (params.poc_only)  qs.set('poc_only', 'true')
  if (params.patch_only) qs.set('patch_only', 'true')
  if (params.epss_min != null) qs.set('epss_min', String(params.epss_min))
  if (params.search)    qs.set('search', params.search)
  if (params.stack)     qs.set('stack', params.stack)
  if (params.vendors)   qs.set('vendors', params.vendors)
  if (params.technique) qs.set('technique', params.technique)
  if (params.published_on) qs.set('published_on', params.published_on)
  if (params.summary_only) qs.set('summary_only', 'true')
  if (params.ai_context_only) qs.set('ai_context_only', 'true')
  if (params.frameworks) qs.set('frameworks', params.frameworks)
  if (params.watchlist_only) qs.set('watchlist_only', 'true')
  if (params.page)      qs.set('page', String(params.page))
  if (params.limit)     qs.set('limit', String(params.limit))
  const query = qs.toString()
  return request(`/cves${query ? `?${query}` : ''}`)
}

/** Embeddings E4/E7 — hybrid / keyword / semantic CVE search (default hybrid). */
export function fetchSemanticSearch({
  q = '',
  mode = 'hybrid',
  limit = 20,
  stack = '',
  severity = '',
  kev_only = false,
} = {}) {
  const qs = new URLSearchParams()
  if (q) qs.set('q', q)
  if (mode) qs.set('mode', mode)
  if (limit != null) qs.set('limit', String(limit))
  if (stack) qs.set('stack', stack)
  if (severity) qs.set('severity', severity)
  if (kev_only) qs.set('kev_only', 'true')
  const query = qs.toString()
  return request(`/search/semantic${query ? `?${query}` : ''}`)
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

export function fetchCVEDrawerBundle(cveId, sector = '') {
  const qs = sector ? `?sector=${encodeURIComponent(sector)}` : ''
  return request(`/cves/${encodeURIComponent(cveId)}/drawer${qs}`)
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

export function fetchCorrelationClusters({ stack = '', limit = 20, includeStale = false } = {}) {
  const qs = new URLSearchParams()
  if (stack) qs.set('stack', stack)
  qs.set('limit', String(limit))
  if (includeStale) qs.set('include_stale', 'true')
  const query = qs.toString()
  return request(`/correlation/clusters${query ? `?${query}` : ''}`)
}

export function fetchCVEGreynoiseScans(cveId) {
  return request(`/cves/${encodeURIComponent(cveId)}/greynoise-scans`)
}

export function suppressCVECorrelation(cveId, body) {
  return request(`/cves/${encodeURIComponent(cveId)}/correlation/suppress`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function fetchCorrelationSuppressions(cveId) {
  return request(`/cves/${encodeURIComponent(cveId)}/correlation/suppressions`)
}

export function restoreCVECorrelation(cveId, { scope, cve_id_b = '', campaign_id = '', pulse_id = '' }) {
  const qs = new URLSearchParams({ scope })
  if (cve_id_b) qs.set('cve_id_b', cve_id_b)
  if (campaign_id) qs.set('campaign_id', campaign_id)
  if (pulse_id) qs.set('pulse_id', pulse_id)
  return request(`/cves/${encodeURIComponent(cveId)}/correlation/suppress?${qs}`, {
    method: 'DELETE',
  })
}

export function fetchCorrelationFeedback(cveId) {
  return request(`/cves/${encodeURIComponent(cveId)}/correlation/feedback`)
}

export function confirmCVECorrelation(cveId, body) {
  return request(`/cves/${encodeURIComponent(cveId)}/correlation/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, verdict: 'confirm' }),
  })
}

export function fetchCVEDetection(cveId, product = '') {
  const qs = product ? `?product=${encodeURIComponent(product)}` : ''
  return request(`/cves/${encodeURIComponent(cveId)}/detection${qs}`)
}

export function fetchCVEMomentum(cveId) {
  return request(`/cves/${encodeURIComponent(cveId)}/momentum`)
}

/** Operational Priority surface — Threat, Environment, OP band (ADR-002). */
export function fetchCVERisk(cveId, { profile, assets } = {}) {
  const body = {}
  if (profile) body.profile = profile
  if (assets?.length) body.assets = assets
  return request(`/cves/${encodeURIComponent(cveId)}/risk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function fetchCVEsForExport(params = {}) {
  const qs = new URLSearchParams()
  if (params.severity)  qs.set('severity', params.severity)
  if (params.kev_only)  qs.set('kev_only', 'true')
  if (params.kev_overdue_only) qs.set('kev_overdue_only', 'true')
  if (params.poc_only)  qs.set('poc_only', 'true')
  if (params.patch_only) qs.set('patch_only', 'true')
  if (params.epss_min != null) qs.set('epss_min', String(params.epss_min))
  if (params.search)    qs.set('search', params.search)
  if (params.stack)     qs.set('stack', params.stack)
  if (params.vendors)   qs.set('vendors', params.vendors)
  if (params.technique) qs.set('technique', params.technique)
  if (params.published_on) qs.set('published_on', params.published_on)
  if (params.summary_only) qs.set('summary_only', 'true')
  if (params.ai_context_only) qs.set('ai_context_only', 'true')
  if (params.frameworks) qs.set('frameworks', params.frameworks)
  if (params.watchlist_only) qs.set('watchlist_only', 'true')
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

/** Forge: MITRE coverage map (stack × techniques × rule status). */
export function fetchForgeCoverage(stack = '') {
  const qs = stack ? `?stack=${encodeURIComponent(stack)}` : ''
  return request(`/forge/coverage${qs}`)
}

/** V1.5: stack-scoped ATT&CK threat scenario cards. */
export function fetchThreatModelScenarios(stack = '') {
  const qs = stack ? `?stack=${encodeURIComponent(stack)}` : ''
  return request(`/threat-model/scenarios${qs}`)
}

/** TM-2: Security Architecture module -- manifest (section index) + overview tiles. */
export function fetchSecurityArchitectureManifest() {
  return request('/security-architecture/manifest')
}

export function fetchSecurityArchitectureOverview() {
  return request('/security-architecture/overview')
}

/** TM-2: generic drill-through read of a manifest section's corpus rows. */
export function fetchSecurityArchitectureSection(sectionId, params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
  ).toString()
  return request(`/security-architecture/section/${encodeURIComponent(sectionId)}${qs ? `?${qs}` : ''}`)
}

/** TM-3: ATT&CK coverage matrix (wraps routers.forge.build_coverage_map -- same query as Forge). */
export function fetchSecurityArchitectureMitre(stack = '') {
  const qs = stack ? `?stack=${encodeURIComponent(stack)}` : ''
  return request(`/security-architecture/mitre${qs}`)
}

/** TM-3: threat scenarios -- stack-scoped (Forge parity) or self-stack toggle (spec §4.5). */
export function fetchSecurityArchitectureThreatScenarios({ stack = '', selfStack = false } = {}) {
  const params = new URLSearchParams()
  if (selfStack) params.set('self_stack', 'true')
  else if (stack) params.set('stack', stack)
  const qs = params.toString()
  return request(`/security-architecture/threat-scenarios${qs ? `?${qs}` : ''}`)
}

/** TM-4: generated system architecture graph (nodes/edges, no layout). */
export function fetchSecurityArchitectureGraph() {
  return request('/security-architecture/graph/architecture')
}

/** TM-4: attack surface -- endpoint inventory x linked controls, counts only. */
export function fetchSecurityArchitectureAttackSurface() {
  return request('/security-architecture/graph/attack-surface')
}

/** TM-4: context-rail payload for a selected architecture-graph node. */
export function fetchSecurityArchitectureNodeContext(nodeId) {
  return request(`/security-architecture/context/${encodeURIComponent(nodeId)}`)
}

/** TM-5: global search over the corpus + live MITRE technique names (spec §5.17). */
export function fetchSecurityArchitectureSearch(q) {
  return request(`/security-architecture/search?q=${encodeURIComponent(q)}`)
}

/** TM-5: every curated record past the review window, across all sections (Stale Records tile drill-through). */
export function fetchSecurityArchitectureStale() {
  return request('/security-architecture/stale')
}

/**
 * TM-6: analyst framework workspace (cwe | owasp | capec | stride) over the
 * user's own live threat surface. `scope` = all | stack | watchlist | kev;
 * `stack` overrides the saved stack for scope=stack; `severity` narrows to one
 * severity. Every row's count drills through to its `example_cves`.
 */
export function fetchSecurityArchitectureFramework(framework, { scope = 'all', stack = '', severity = '' } = {}) {
  const params = new URLSearchParams({ scope })
  if (stack) params.set('stack', stack)
  if (severity) params.set('severity', severity)
  return request(`/security-architecture/frameworks/${encodeURIComponent(framework)}?${params.toString()}`)
}

/** V1.5: run Sigma rule against pasted log lines (file-based proof bench). */
export function runProofBench({ lines, sigmaYaml, patterns, maxSamples = 10 }) {
  const body = { lines, max_samples: maxSamples }
  if (sigmaYaml) body.sigma_yaml = sigmaYaml
  if (patterns?.length) body.patterns = patterns
  return request('/proof/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

/** V1.5: KEV-driven detection backlog (gap items on operator stack). */
export function fetchDetectionBacklog({ status = 'open', stack = '' } = {}) {
  const params = new URLSearchParams({ status })
  if (stack) params.set('stack', stack)
  return request(`/detection-backlog?${params}`)
}

export function dismissDetectionBacklogItem(itemId) {
  return request(`/detection-backlog/${itemId}/dismiss`, { method: 'POST' })
}

/** Forge: hunt pack content for one ATT&CK technique. */
export function fetchHuntPack(techniqueId) {
  return request(`/hunt-packs/${encodeURIComponent(techniqueId)}`)
}

/** Forge Library (FR-2): list saved hunt packs, paginated + filterable. */
export function fetchHuntPacks({ techniqueId, cveId, priority, q, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (techniqueId) params.set('technique_id', techniqueId)
  if (cveId) params.set('cve_id', cveId)
  if (priority) params.set('priority', priority)
  if (q) params.set('q', q)
  return request(`/hunt-packs?${params}`)
}

/** Forge Library (FR-2): delete one saved hunt pack (hard delete, audited). */
export function deleteHuntPack(packId) {
  return request(`/hunt-packs/${encodeURIComponent(packId)}`, { method: 'DELETE' })
}

/** Forge: generate + persist a detection pack for a CVE (CVE→pack link). */
export function generateHuntPack(cveId, techniqueId = '') {
  const body = techniqueId
    ? { cve_id: cveId, technique_id: techniqueId }
    : { cve_id: cveId }
  return request('/hunt-packs/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function fetchKEVDeadlines(sort = 'recent') {
  return request(`/kev/deadlines?sort=${sort}`)
}

export function fetchTopVendors(limit = 10) {
  return request(`/stats/top-vendors?limit=${limit}`)
}

export function fetchChanges({ field = null, sinceHours = null, since_hours = null, limit = 50 } = {}) {
  const qs = new URLSearchParams()
  qs.set('since_hours', String(since_hours ?? sinceHours ?? 24))
  qs.set('limit', String(limit))
  if (field) qs.set('field', field)
  return request(`/changes?${qs}`)
}

export function fetchRiskWeights() {
  return request('/config/risk')
}

export function fetchBrief({ stack = '', sinceHours = 24, limit = 10, kevDueDays = 14 } = {}) {
  const qs = new URLSearchParams()
  qs.set('since_hours', String(sinceHours))
  qs.set('limit', String(limit))
  qs.set('kev_due_days', String(kevDueDays))
  if (stack?.trim()) qs.set('stack', stack.trim())
  return request(`/brief?${qs}`)
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

export function fetchIocWatchlist() {
  return request('/ioc/watchlist')
}

export function addIocWatchlist({ value, type, label = '' }) {
  return request('/ioc/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value, type, label }),
  })
}

export function removeIocWatchlist(entryId) {
  return request(`/ioc/watchlist/${entryId}`, { method: 'DELETE' })
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

/** CVE watchlist — pin / snooze (server-backed, single-user). */
export function fetchWatchlist() {
  return request('/watchlist')
}

export function setWatchlistEntry(cveId, state, snoozeDays = null) {
  const body = { cve_id: cveId, state }
  if (state === 'snooze' && snoozeDays != null) {
    body.snooze_days = snoozeDays
  }
  return request('/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function removeWatchlistEntry(cveId) {
  return request(`/watchlist/${encodeURIComponent(cveId)}`, { method: 'DELETE' })
}

export function clearAllSnoozes() {
  return request('/watchlist/snoozes', { method: 'DELETE' })
}

// ── Wallboard (read-only kiosk) ────────────────────────────────────────────

export function getWallboardToken() {
  return sessionStorage.getItem('briefr-wallboard-token') || ''
}

export function setWallboardToken(token) {
  sessionStorage.setItem('briefr-wallboard-token', token)
}

export function clearWallboardToken() {
  sessionStorage.removeItem('briefr-wallboard-token')
}

export async function createWallboardSession(token) {
  const res = await fetch('/api/wallboard/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ token }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const err = new Error(data.detail || res.statusText || 'Session failed')
    err.status = res.status
    throw err
  }
  return res.json()
}

export async function clearWallboardSession() {
  await fetch('/api/wallboard/session', { method: 'DELETE', credentials: 'include' })
}

export function fetchWallboard() {
  const token = getWallboardToken()
  const headers = {}
  if (token) headers['X-BRIEFR-Wallboard-Token'] = token
  return request('/wallboard', { headers, credentials: 'include' })
}

// ── Admin API ──────────────────────────────────────────────────────────────

/** Authenticated fetch returning the raw Response (callers that need headers
    like X-Request-ID). Retries once via /auth/refresh on 401, same as
    request(); dispatches briefr-auth-expired when the session is gone. */
export async function authedFetch(path, opts = {}, _retried = false) {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    credentials: 'include',
    signal: opts.signal ?? AbortSignal.timeout(60_000),
  })
  if (res.status === 401) {
    if (!_retried && (await refreshAccessToken())) {
      return authedFetch(path, opts, true)
    }
    window.dispatchEvent(new CustomEvent('briefr-auth-expired'))
    throw Object.assign(new Error('Unauthorized'), { status: 401 })
  }
  return res
}

function adminFetch(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) }
  return authedFetch(`/admin${path}`, { ...opts, headers })
}

export function getAdminRequestId(res) {
  return res?.headers?.get?.('X-Request-ID') || null
}

/** Parse admin Response; throw on HTTP error with requestId attached. */
export async function adminJson(res) {
  const requestId = getAdminRequestId(res)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = data?.detail
    const message = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map(d => d.msg || String(d)).join('; ')
        : `HTTP ${res.status}`
    const err = new Error(message)
    err.status = res.status
    err.requestId = requestId
    err.data = data
    throw err
  }
  return { data, requestId, response: res }
}

export const adminApi = {
  get: (path) => adminFetch(path),
  post: (path, body) => adminFetch(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: (path, body) => adminFetch(path, { method: 'PATCH', body: JSON.stringify(body) }),
  put: (path, body) => adminFetch(path, { method: 'PUT', body: JSON.stringify(body) }),
  del: (path, params) => {
    let url = path
    if (params && Object.keys(params).length) {
      url += `?${new URLSearchParams(params)}`
    }
    return adminFetch(url, { method: 'DELETE' })
  },
  postForm: (path, formData) => adminFetch(path, {
    method: 'POST',
    headers: {},
    body: formData,
  }),
  getJson: async (path) => adminJson(await adminFetch(path)),
  postJson: async (path, body) => adminJson(await adminFetch(path, { method: 'POST', body: JSON.stringify(body) })),
  patchJson: async (path, body) => adminJson(await adminFetch(path, { method: 'PATCH', body: JSON.stringify(body) })),
  putJson: async (path, body) => adminJson(await adminFetch(path, { method: 'PUT', body: JSON.stringify(body) })),
  delJson: async (path, params) => {
    let url = path
    if (params && Object.keys(params).length) {
      url += `?${new URLSearchParams(params)}`
    }
    return adminJson(await adminFetch(url, { method: 'DELETE' }))
  },
  listOutboundJobs: (limit = 50) => adminApi.getJson(outboundJobsPath(limit).slice('/api/admin'.length)),
}
