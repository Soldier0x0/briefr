/** Procrastinate queue statuses (raw DB values → operator-facing labels). */

export const OUTBOUND_STATUS_CATALOG = {
  todo: {
    operator: 'QUEUED',
    analyst: 'Queued',
    hint: 'Waiting for a worker — will run when a slot is free',
    badge: 'badge-warn',
  },
  doing: {
    operator: 'RUNNING',
    analyst: 'In progress',
    hint: 'Task is executing now (durable queue — survives backend restarts)',
    badge: 'badge-info',
  },
  succeeded: {
    operator: 'SUCCEEDED',
    analyst: 'Done',
    hint: 'Finished successfully',
    badge: 'badge-ok',
  },
  failed: {
    operator: 'FAILED',
    analyst: 'Failed',
    hint: 'Finished with an error — check backend logs for this job id',
    badge: 'badge-error',
  },
  aborted: {
    operator: 'CANCELLED',
    analyst: 'Cancelled',
    hint: 'Stopped before completion',
    badge: 'badge-error',
  },
}

export function normalizeOutboundStatus(status) {
  return String(status || '').toLowerCase()
}

export function outboundStatusLabel(status, mode = 'operator') {
  const key = normalizeOutboundStatus(status)
  const entry = OUTBOUND_STATUS_CATALOG[key]
  if (!entry) return status || '—'
  return mode === 'analyst' ? entry.analyst : entry.operator
}

export function outboundStatusHint(status) {
  const key = normalizeOutboundStatus(status)
  const entry = OUTBOUND_STATUS_CATALOG[key]
  const hint = entry?.hint
  if (!hint) return ''
  if (!status || key === String(status).toLowerCase()) return hint
  return `${hint} (queue status: ${status})`
}

export function outboundStatusBadgeClass(status) {
  const key = normalizeOutboundStatus(status)
  return OUTBOUND_STATUS_CATALOG[key]?.badge || 'badge-muted'
}
