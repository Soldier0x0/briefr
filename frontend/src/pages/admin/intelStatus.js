// Pure derivation helpers for the Analyst "Intel status" view.
import { sourceLabel } from './formatters.js'
import { fmtAge } from './formatters.js'
import { jobLabel } from './catalog.js'
import { CIRCUIT_UI } from './circuitLabels.js'

export const ANALYST_SCHEDULE_TABLE_JOB_IDS = [
  'nvd_incremental_sync',
  'kev_metadata_sync',
  'epss_score_sync',
  'weekly_mitre_refresh',
  'incident_feed_refresh',
  'nightly_correlation',
]

const NVD_AMBER_SECONDS = 7200
const NVD_RED_SECONDS = 14400

export function worstSource(system) {
  const sources = system?.feeds?.sources || {}
  const open = Object.entries(sources).filter(([, s]) => s.circuit_open)
  if (open.length === 0) return null
  const [key] = open.sort(([, a], [, b]) => (b.consecutive_failures || 0) - (a.consecutive_failures || 0))[0]
  return sourceLabel(key)
}

function nvdJob(system) {
  return system?.scheduler_jobs?.find(j => j.id === 'nvd_incremental_sync')
}

export function nvdCadenceLabel(system) {
  const job = nvdJob(system)
  return job?.schedule_cadence || 'Scheduled interval'
}

export function nvdStaleDetail(system) {
  const age = system?.last_nvd_sync_age_seconds
  if (age == null) return null
  const cadence = nvdCadenceLabel(system)
  return `NIST CVE feed — ${fmtAge(age)} since last sync (expected ${cadence.toLowerCase()})`
}

export function collectHealthIssues(system) {
  if (!system) return []
  const issues = []
  const nvdAge = system.last_nvd_sync_age_seconds
  if (nvdAge != null && nvdAge > NVD_AMBER_SECONDS) {
    issues.push(nvdStaleDetail(system))
  }
  const sources = system.feeds?.sources || {}
  for (const [key, s] of Object.entries(sources)) {
    if (s.circuit_open) {
      issues.push(CIRCUIT_UI.intelIssue(sourceLabel(key), s.consecutive_failures || 0))
    }
  }
  if (system.feeds?.incidents?.stale) {
    issues.push('Incident news feed — snapshot is stale')
  }
  for (const err of system.recent_errors || []) {
    issues.push(`Scheduler job failed — ${jobLabel(err.job_id, 'analyst')}`)
  }
  if (system.db_integrity?.ok === false) {
    issues.push('Database integrity check failed on last startup')
  }
  return issues.filter(Boolean)
}

export function overallHealth(system) {
  if (!system) return { level: 'green', headline: 'Intel looks current', detail: 'Loading…', issues: [] }

  const issues = collectHealthIssues(system)
  const dbFailed = system.db_integrity?.ok === false
  const jobErrors = system.jobs_with_errors_count || 0
  const openCircuits = system.open_circuit_count || 0
  const nvdAged = system.last_nvd_sync_age_seconds != null && system.last_nvd_sync_age_seconds > NVD_AMBER_SECONDS

  if (dbFailed || (openCircuits > 0 && jobErrors > 0)) {
    return {
      level: 'red',
      headline: 'Intel may be unreliable',
      detail: issues[0] || 'Multiple sources are failing.',
      issues,
    }
  }

  if (issues.length > 0) {
    return {
      level: nvdAged && issues.length === 1 ? 'amber' : issues.some(i => i.includes('paused after')) ? 'red' : 'amber',
      headline: issues.length === 1 ? issues[0] : `${issues.length} items need attention`,
      detail: issues.length === 1 ? 'See details below.' : issues.join(' · '),
      issues,
    }
  }

  return {
    level: 'green',
    headline: 'Intel looks current',
    detail: 'All sources are within expected windows.',
    issues: [],
  }
}

export function nvdAgeColor(seconds) {
  if (seconds == null) return ''
  if (seconds <= NVD_AMBER_SECONDS) return 'color-green'
  if (seconds <= NVD_RED_SECONDS) return 'color-amber'
  return 'color-red'
}

export function analystScheduleJobs(jobs) {
  if (!jobs) return []
  return jobs.filter(j => ANALYST_SCHEDULE_TABLE_JOB_IDS.includes(j.id) || j.last_run_had_error === true)
}
