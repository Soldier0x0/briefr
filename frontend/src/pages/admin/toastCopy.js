import { jobLabel } from './catalog.js'

/** Lifecycle-aware operator/analyst toast copy for scheduler actions. */

export function schedulerJobStarted(jobId, mode = 'operator') {
  return `${jobLabel(jobId, mode)} started in background`
}

export function schedulerJobManualRun(jobId, mode = 'operator') {
  return `Manual run started — ${jobLabel(jobId, mode)}`
}

export function schedulerJobRefresh(jobId, mode = 'analyst') {
  return `${jobLabel(jobId, mode)} refresh started`
}

export function schedulerJobPaused(jobId, mode = 'operator') {
  return `${jobLabel(jobId, mode)} paused`
}

export function schedulerJobResumed(jobId, mode = 'operator') {
  return `${jobLabel(jobId, mode)} resumed`
}

export function schedulerJobRetry(jobId, mode = 'operator') {
  return `Retry started — ${jobLabel(jobId, mode)}`
}
