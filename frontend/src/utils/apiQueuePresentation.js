/** Presentation helpers for API queue indicator — state priority and analyst copy. */

export const STATE_PRIORITY = {
  'rate_limited': 4,
  waiting: 3,
  queued: 2,
  active: 1,
}

export const STATE_LABELS = {
  active: 'ACTIVE',
  queued: 'QUEUED',
  waiting: 'WAITING',
  rate_limited: 'RATE LIMITED',
}

const WAIT_REASON_FALLBACK = 'Waiting for provider slot'

/** Map backend wait_reason (already analyst-facing) to detail line copy. */
export function formatWaitDetail(waitReason, state, retryInSeconds, elapsedSeconds) {
  if (state === 'active') {
    return `Running ${formatElapsed(elapsedSeconds)}`
  }
  if (state === 'rate_limited') {
    if (retryInSeconds != null && retryInSeconds > 0) {
      return `Retry in ${formatElapsed(retryInSeconds)}`
    }
    return waitReason || 'Provider rate limit'
  }
  if (state === 'waiting') {
    if (waitReason) {
      const pacing = waitReason.toLowerCase().includes('pacing')
      if (pacing && elapsedSeconds != null) {
        return `${waitReason} · ${formatElapsed(elapsedSeconds)}`
      }
      return waitReason
    }
    return WAIT_REASON_FALLBACK
  }
  if (state === 'queued') {
    return waitReason || WAIT_REASON_FALLBACK
  }
  return waitReason || ''
}

export function formatElapsed(seconds) {
  const n = Number(seconds)
  if (!Number.isFinite(n) || n < 0) return '0s'
  if (n < 60) return `${n.toFixed(n >= 10 ? 0 : 1)}s`
  const mins = Math.floor(n / 60)
  const secs = Math.round(n % 60)
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`
}

export function formatSourceLabel(key) {
  return String(key || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

export function highestQueueState(requests = [], sources = {}) {
  let best = null
  let bestPriority = 0

  const reqs = Array.isArray(requests) ? requests : []
  for (const req of reqs) {
    const state = String(req?.state || '').toLowerCase()
    const p = STATE_PRIORITY[state] || 0
    if (p > bestPriority) {
      bestPriority = p
      best = state
    }
  }

  if (!best) {
    const srcMap = sources && typeof sources === 'object' ? sources : {}
    for (const info of Object.values(srcMap)) {
      if (info?.paused_for_seconds > 0) return 'rate_limited'
      if (info?.queued > 0) return 'queued'
      if (info?.active > 0) return 'active'
    }
  }

  return best || null
}

export function indicatorTone(state) {
  switch (state) {
    case 'rate_limited':
      return 'throttled'
    case 'waiting':
    case 'queued':
      return 'pending'
    case 'active':
      return 'active'
    default:
      return 'pending'
  }
}

export function buildQueueRows(apiQueue) {
  const requests = apiQueue?.requests
  if (Array.isArray(requests) && requests.length > 0) {
    return requests.map(req => ({
      key: req.request_id || `${req.source}-${req.operation}-${req.context_id}`,
      source: formatSourceLabel(req.source),
      state: String(req.state || 'queued').toLowerCase(),
      stateLabel: STATE_LABELS[req.state] || String(req.state || '').toUpperCase(),
      displayLabel: req.display_label || '',
      contextId: req.context_id || null,
      detail: formatWaitDetail(
        req.wait_reason,
        String(req.state || '').toLowerCase(),
        req.retry_in_seconds,
        req.elapsed_seconds,
      ),
    }))
  }

  const sources = apiQueue?.sources ?? {}
  return Object.entries(sources).map(([key, info]) => {
    let state = 'active'
    if (info.paused_for_seconds > 0) state = 'rate_limited'
    else if (info.queued > 0) state = 'queued'
    else if (info.active > 0) state = 'active'

    const meta = [
      info.queued > 0 && `${info.queued} queued`,
      info.active > 0 && `${info.active} active`,
      info.paused_for_seconds > 0 && `retry in ${formatElapsed(info.paused_for_seconds)}`,
    ].filter(Boolean).join(' · ')

    return {
      key,
      source: formatSourceLabel(key),
      state,
      stateLabel: STATE_LABELS[state] || state.toUpperCase(),
      displayLabel: meta || 'Outbound API activity',
      contextId: null,
      detail: formatWaitDetail(null, state, info.paused_for_seconds, null),
      fallback: true,
    }
  })
}

export function summarizeQueue(apiQueue) {
  const queued = apiQueue?.total_queued ?? 0
  const active = apiQueue?.total_active ?? 0
  const count = queued + active
  const rows = buildQueueRows(apiQueue)
  const toneState = highestQueueState(apiQueue?.requests, apiQueue?.sources)

  const parts = []
  const waitingCount = rows.filter(r => r.state === 'queued' || r.state === 'waiting').length
  const throttledCount = rows.filter(r => r.state === 'rate_limited').length

  if (throttledCount > 0) {
    parts.push(`${throttledCount} API request${throttledCount === 1 ? '' : 's'} rate limited`)
  }
  if (waitingCount > 0) {
    parts.push(`${waitingCount} API request${waitingCount === 1 ? '' : 's'} waiting`)
  }
  if (active > 0) {
    parts.push(`${active} API request${active === 1 ? '' : 's'} active`)
  }
  if (!parts.length && count > 0) {
    parts.push(`${count} API request${count === 1 ? '' : 's'} queued or in progress`)
  }

  return {
    queued,
    active,
    count,
    toneState,
    tone: indicatorTone(toneState),
    ariaLabel: parts.join(', ') || 'API queue idle',
    rows,
  }
}

export function handleApiQueueDropdownKeyDown(event, setOpen) {
  if (event?.key === 'Escape') {
    setOpen(false)
  }
}
