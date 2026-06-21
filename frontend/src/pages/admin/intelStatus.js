// Pure derivation helpers for the Analyst "Intel status" view.
// No new API calls — everything is computed from the existing GET /api/admin/system payload.
import { sourceLabel } from './formatters.js'

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

export function overallHealth(system) {
  if (!system) return { level: 'green', headline: 'Intel looks current', detail: 'Loading…' }

  const dbFailed = system.db_integrity?.ok === false
  const nvdAge = system.last_nvd_sync_age_seconds
  const openCircuits = system.open_circuit_count || 0
  const incidentsStale = system.feeds?.incidents?.stale === true
  const jobErrors = system.jobs_with_errors_count || 0

  const failureCount = [openCircuits > 0, jobErrors > 0, incidentsStale].filter(Boolean).length

  if (dbFailed || failureCount >= 2) {
    return {
      level: 'red',
      headline: 'Intel may be unreliable',
      detail: dbFailed ? 'The database file may be damaged.' : 'Multiple sources are failing — see details below.',
    }
  }

  const nvdAged = nvdAge != null && nvdAge > NVD_AMBER_SECONDS
  if (nvdAged || openCircuits > 0 || incidentsStale) {
    const worst = worstSource(system)
    return {
      level: 'amber',
      headline: 'Some sources are delayed',
      detail: worst ? `${worst} is unavailable — see details below.` : 'See details below.',
    }
  }

  return {
    level: 'green',
    headline: 'Intel looks current',
    detail: 'All sources are within expected windows.',
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
