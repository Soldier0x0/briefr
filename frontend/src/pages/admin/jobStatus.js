import { jobLabel, statusLabel } from './catalog.js'

/** True when a scheduler job is actively executing (lock held). */
export function isJobRunning(job) {
  return job?.status === 'LOCKED' || job?.lock_held === true
}

/**
 * Single job list for all admin surfaces — prefer polled system.scheduler_jobs,
 * reconcile with active_locks so LOCKED/RUNNING is consistent everywhere.
 */
export function getSchedulerJobs(system, fallbackJobs) {
  const jobs = system?.scheduler_jobs?.length ? system.scheduler_jobs : fallbackJobs
  if (!jobs?.length) return jobs ?? null
  const lockedIds = new Set((system?.active_locks || []).map((l) => l.job_id))
  return jobs.map((job) => {
    if (!lockedIds.has(job.id) || job.status === 'DISABLED') return job
    if (job.status === 'LOCKED') return job
    return { ...job, status: 'LOCKED', lock_held: true }
  })
}

export function getRunningJobs(system, fallbackJobs) {
  return (getSchedulerJobs(system, fallbackJobs) || []).filter(isJobRunning)
}

export function jobById(jobs, jobId) {
  return (jobs || []).find((j) => j.id === jobId)
}

export function formatRunningJobLine(jobId, mode = 'operator') {
  return `${jobLabel(jobId, mode)} — ${statusLabel('LOCKED', mode)}`
}
