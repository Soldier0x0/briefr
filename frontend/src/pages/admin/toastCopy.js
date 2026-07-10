import { jobLabel } from './catalog.js'

/** Lifecycle-aware operator/analyst toast copy for scheduler actions. */

function displayName(jobId, mode) {
  return jobLabel(jobId, mode) || jobId
}

export function schedulerJobStarted(jobId, mode = 'operator') {
  return `${displayName(jobId, mode)} started in background`
}

export function schedulerJobManualRun(jobId, mode = 'operator') {
  return `Manual run started — ${displayName(jobId, mode)}`
}

export function schedulerJobRefresh(jobId, mode = 'analyst') {
  return `${displayName(jobId, mode)} refresh started`
}

export function schedulerJobPaused(jobId, mode = 'operator') {
  return `${displayName(jobId, mode)} paused`
}

export function schedulerJobResumed(jobId, mode = 'operator') {
  return `${displayName(jobId, mode)} resumed`
}

export function schedulerJobRetry(jobId, mode = 'operator') {
  return `Retry started — ${displayName(jobId, mode)}`
}
