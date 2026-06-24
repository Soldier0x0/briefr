const STORAGE_KEY = 'briefr-admin-job-acks'

export function jobErrorAckKey(jobId, lastRunUtc) {
  return `${jobId}|${lastRunUtc || ''}`
}

export function loadJobAcks() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(raw) ? raw : []
  } catch {
    return []
  }
}

export function saveJobAcks(acks) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(acks))
  } catch {
    // storage unavailable
  }
}

export function filterUnacknowledgedErrors(recentErrors, acks) {
  const seen = new Set(acks)
  return (recentErrors || []).filter(
    e => !seen.has(jobErrorAckKey(e.job_id, e.last_run_utc)),
  )
}

export function markAllJobErrorsRead(recentErrors) {
  const set = new Set(loadJobAcks())
  for (const e of recentErrors || []) {
    set.add(jobErrorAckKey(e.job_id, e.last_run_utc))
  }
  const next = [...set]
  saveJobAcks(next)
  return next
}
