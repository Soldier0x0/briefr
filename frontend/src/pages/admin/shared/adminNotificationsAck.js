const STORAGE_KEY = 'briefr:notifications:acked'

export function notificationEventKey(evt) {
  if (!evt?.type) return ''
  if (evt.type === 'audit') return `audit:${evt.id}`
  if (evt.type === 'job_error') return `job_error:${evt.job_id}:${evt.summary || ''}`
  if (evt.type === 'api_key_unhealthy') {
    return `api_key:${evt.provider}:${evt.summary || ''}`
  }
  return `${evt.type}:${evt.id || evt.job_id || evt.provider || ''}`
}

export function isActionableNotification(evt) {
  return evt?.type === 'job_error' || evt?.type === 'api_key_unhealthy'
}

export function loadAckedKeys() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw)
    return new Set(Array.isArray(parsed) ? parsed : [])
  } catch {
    return new Set()
  }
}

function persistAckedKeys(keys) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...keys]))
}

export function ackNotification(acked, evt) {
  const key = notificationEventKey(evt)
  if (!key) return acked
  const next = new Set(acked)
  next.add(key)
  persistAckedKeys(next)
  return next
}

export function ackAllNotifications(acked, events) {
  const next = new Set(acked)
  for (const evt of events || []) {
    const key = notificationEventKey(evt)
    if (key) next.add(key)
  }
  persistAckedKeys(next)
  return next
}

export function countUnackedActionable(events, acked) {
  return (events || []).filter(
    evt => isActionableNotification(evt) && !acked.has(notificationEventKey(evt)),
  ).length
}
