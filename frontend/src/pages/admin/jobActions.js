/** Scheduler job action matrix — shared by JobTable, Overview, Scheduler pages. */

export function canRunNow(status) {
  return status !== 'LOCKED' && status !== 'DISABLED'
}

export function canPauseResume(status) {
  return status === 'ACTIVE' || status === 'PAUSED'
}

export function pauseResumeAction(status) {
  if (status === 'PAUSED') return 'resume'
  if (status === 'ACTIVE') return 'pause'
  return null
}

export function nextRunCell(status, nextRunIso, fmtIso) {
  if (status === 'PAUSED') return '(paused)'
  if (status === 'DISABLED') return '(disabled)'
  return fmtIso(nextRunIso)
}

export function nextRunTitle(status) {
  if (status === 'PAUSED') return 'Job is paused — will not run until resumed'
  if (status === 'DISABLED') return 'Job is turned off in configuration — enable the matching setting under API keys & config'
  return undefined
}
