import { sourceLabel, fmtAge } from './formatters.js'
import { jobLabel } from './catalog.js'
import { nvdStaleDetail } from './intelStatus.js'
import { CIRCUIT_UI } from './circuitLabels.js'

const NVD_AMBER_SECONDS = 7200
const NVD_RED_SECONDS = 14400

/**
 * Aggregated operator/analyst attention items for the overview landing (E8-3).
 * Each item links to the admin page that best resolves it.
 */
export function collectNeedsAttentionItems(
  system,
  {
    ingestErrorCount = 0,
    unackJobErrorCount = 0,
    mode = 'operator',
  } = {},
) {
  if (!system) return []

  const items = []

  if (system.db_integrity?.ok === false) {
    items.push({
      id: 'db-integrity',
      severity: 'error',
      title: 'Database integrity check failed',
      detail: 'Last startup probe reported a problem — verify before relying on intel.',
      pageId: 'database',
      actionLabel: 'Open database',
    })
  }

  const sources = system.feeds?.sources || {}
  for (const [key, source] of Object.entries(sources)) {
    if (!source.circuit_open) continue
    const failures = source.consecutive_failures || 0
    items.push({
      id: `circuit-${key}`,
      severity: 'error',
      title: `${sourceLabel(key)} temporarily unavailable`,
      detail: CIRCUIT_UI.needsAttentionDetail(failures),
      pageId: 'feedhealth',
      actionLabel: 'View feed health',
    })
  }

  for (const webhook of system.webhooks?.failing || []) {
    items.push({
      id: `webhook-${webhook.id}`,
      severity: 'error',
      title: `Webhook delivery failing — ${webhook.name || webhook.id}`,
      detail: webhook.last_error || 'Recent delivery attempts failed.',
      pageId: 'webhooks',
      actionLabel: 'Open webhooks',
    })
  }

  if (unackJobErrorCount > 0) {
    items.push({
      id: 'scheduler-errors',
      severity: 'error',
      title:
        unackJobErrorCount === 1
          ? '1 scheduler job failed'
          : `${unackJobErrorCount} scheduler jobs failed`,
      detail: 'Review recent job errors and retry or pause affected pipelines.',
      pageId: mode === 'analyst' ? 'overview' : 'scheduler',
      actionLabel: mode === 'analyst' ? 'Review below' : 'Open scheduler',
    })
  }

  if (ingestErrorCount > 0) {
    items.push({
      id: 'ingest-errors',
      severity: 'warning',
      title:
        ingestErrorCount === 1
          ? '1 application log error'
          : `${ingestErrorCount} application log errors`,
      detail: 'Recent ERROR/CRITICAL lines in the application log.',
      pageId: 'ingestlog',
      actionLabel: 'View logs',
    })
  }

  const failedAuth = system.failed_auth_last_24h || 0
  if (failedAuth > 0) {
    items.push({
      id: 'failed-auth',
      severity: 'warning',
      title:
        failedAuth === 1
          ? '1 failed login attempt (24h)'
          : `${failedAuth} failed login attempts (24h)`,
      detail: 'Review authentication events for brute-force or misconfigured clients.',
      pageId: 'security',
      actionLabel: 'Open security',
    })
  }

  const nvdAge = system.last_nvd_sync_age_seconds
  if (nvdAge != null && nvdAge > NVD_AMBER_SECONDS) {
    items.push({
      id: 'nvd-stale',
      severity: nvdAge > NVD_RED_SECONDS ? 'error' : 'warning',
      title: 'NIST CVE feed is stale',
      detail: nvdStaleDetail(system) || `Last sync ${fmtAge(nvdAge)} ago.`,
      pageId: 'feedhealth',
      actionLabel: 'View feed health',
    })
  }

  const backupAge = system.last_backup_age_seconds
  const backupThreshold = system.backup_threshold_seconds || 43200
  if (backupAge != null && backupAge > backupThreshold * 0.75) {
    items.push({
      id: 'backup-stale',
      severity: backupAge > backupThreshold ? 'error' : 'warning',
      title: backupAge > backupThreshold ? 'Backup is overdue' : 'Backup approaching threshold',
      detail: `Last backup ${fmtAge(backupAge)} ago (threshold ${Math.round(backupThreshold / 3600)}h).`,
      pageId: 'backups',
      actionLabel: 'Open backups',
    })
  }

  if (system.feeds?.incidents?.stale) {
    items.push({
      id: 'incidents-stale',
      severity: 'warning',
      title: 'Incident news feed is stale',
      detail: 'RSS snapshot has not refreshed within the expected window.',
      pageId: 'feedhealth',
      actionLabel: 'View feed health',
    })
  }

  const severityRank = { error: 0, warning: 1 }
  return items.sort(
    (a, b) => (severityRank[a.severity] ?? 2) - (severityRank[b.severity] ?? 2),
  )
}
