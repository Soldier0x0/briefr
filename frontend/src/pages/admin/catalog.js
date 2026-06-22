// Single source of truth for human-readable labels across Analyst/Operator mode.
// Job ids must match backend/scheduler.py add_job(id=...) and backend/routers/admin.py _JOB_LOCK_MAP.

export const JOB_CATALOG = {
  nvd_incremental_sync: {
    label: 'NIST CVE feed',
    short: 'NVD',
    operatorName: 'NVD Incremental Sync',
    analystDescription: 'New and updated CVEs from NIST.',
    refreshButton: 'Refresh NVD',
  },
  kev_metadata_sync: {
    label: 'Known exploited vulnerabilities',
    short: 'KEV',
    operatorName: 'KEV Metadata Sync',
    analystDescription: "CISA's list of vulnerabilities being actively exploited.",
    refreshButton: 'Refresh KEV',
  },
  epss_score_sync: {
    label: 'Exploit prediction scores',
    short: 'EPSS',
    operatorName: 'EPSS Score Sync',
    analystDescription: 'Likelihood scores for which CVEs get exploited.',
    refreshButton: 'Refresh EPSS',
  },
  weekly_mitre_refresh: {
    label: 'MITRE ATT&CK + ATLAS',
    short: 'MITRE',
    operatorName: 'Weekly MITRE ATT&CK + ATLAS Refresh',
    analystDescription: 'Adversary technique and AI-attack reference data.',
    refreshButton: 'Refresh MITRE',
  },
  atlas_version_check: {
    label: 'ATLAS upstream version check',
    short: 'ATLAS',
    operatorName: 'ATLAS Upstream Version Check',
    analystDescription: 'Checks for new MITRE ATLAS releases and refreshes data automatically when found.',
    refreshButton: 'Check ATLAS version',
  },
  otx_nightly_correlation: {
    label: 'Threat campaign correlation',
    short: 'OTX',
    operatorName: 'OTX Nightly Campaign Correlation',
    analystDescription: 'Links CVEs to known threat campaigns from OTX.',
    refreshButton: 'Refresh campaign links',
  },
  incident_feed_refresh: {
    label: 'Incident news feed',
    short: 'Incidents',
    operatorName: 'Incident Feed Snapshot Refresh',
    analystDescription: 'Security incident headlines from RSS sources.',
    refreshButton: 'Refresh incidents',
  },
  nightly_correlation: {
    label: 'Nightly correlation engine',
    short: 'Correlation',
    operatorName: 'BRIEFR Nightly Correlation Engine',
    analystDescription: 'Cross-references CVEs, exploits, and incidents.',
    refreshButton: 'Run correlation',
  },
  vulnrichment_snapshot_sync: {
    label: 'CISA vulnerability enrichment',
    short: 'Vulnrichment',
    operatorName: 'CISA Vulnrichment Snapshot Sync',
    analystDescription: 'Extra CVE context CISA adds beyond NIST.',
    refreshButton: 'Refresh enrichment',
  },
  cvelistv5_incremental_sync: {
    label: 'CVE list updates',
    short: 'CVE List V5',
    operatorName: 'cvelistV5 Incremental Sync',
    analystDescription: "MITRE's raw CVE record updates.",
    refreshButton: 'Refresh CVE list',
  },
  embeddings_backfill: {
    label: 'CVE description search index',
    short: 'Embeddings',
    operatorName: 'CVE Description Embeddings Backfill',
    analystDescription: 'Builds the semantic search index for CVE text.',
    refreshButton: 'Rebuild search index',
  },
  llm_product_extraction: {
    label: 'Affected-product extraction',
    short: 'LLM extraction',
    operatorName: 'LLM Product Extraction (NVD-unanalyzed CVEs)',
    analystDescription: 'Uses an LLM to identify affected products in CVEs.',
    refreshButton: 'Run extraction',
  },
  exploit_sources_sync: {
    label: 'Public exploit availability',
    short: 'Exploits',
    operatorName: 'Exploit Availability Sources Sync',
    analystDescription: 'Checks ExploitDB, Metasploit, Nuclei, and PoC repos.',
    refreshButton: 'Refresh exploit sources',
  },
  backup_deadman_check: {
    label: 'Backup health check',
    short: 'Backups',
    operatorName: 'Backup Dead-Man Check',
    analystDescription: 'Confirms backups are still running on schedule.',
    refreshButton: 'Check backups',
  },
  scheduled_backup: {
    label: 'Scheduled backup',
    short: 'Backup',
    operatorName: 'Scheduled Backup',
    analystDescription: 'Creates a backup archive and prunes old ones, on BACKUP_INTERVAL_HOURS.',
    refreshButton: 'Run backup',
  },
}

export function jobLabel(id, mode = 'operator') {
  const entry = JOB_CATALOG[id]
  if (!entry) return id
  return mode === 'analyst' ? entry.label : entry.operatorName
}

export function jobShort(id) {
  return JOB_CATALOG[id]?.short || id
}

export function jobRefreshLabel(id) {
  return JOB_CATALOG[id]?.refreshButton || 'Refresh'
}

export const STATUS_CATALOG = {
  ACTIVE: {
    analyst: 'Scheduled',
    operator: 'ACTIVE',
    hint: 'Runs automatically on its timer',
  },
  PAUSED: {
    analyst: 'Paused',
    operator: 'PAUSED',
    hint: 'Will not run until resumed',
  },
  LOCKED: {
    analyst: 'Updating',
    operator: 'RUNNING',
    hint: 'Sync in progress — avoid restarting the server',
  },
  DISABLED: {
    analyst: 'Turned off',
    operator: 'DISABLED',
    hint: 'Disabled in configuration',
  },
}

export function statusLabel(status, mode = 'operator') {
  const entry = STATUS_CATALOG[status]
  if (!entry) return status
  return mode === 'analyst' ? entry.analyst : entry.operator
}

export function statusHint(status) {
  return STATUS_CATALOG[status]?.hint || ''
}

export const TERM_GLOSSARY = {
  db_integrity: {
    analyst: 'Database health',
    operator: 'DB integrity',
    explanation: 'Checks whether the database file is corrupted — not whether CVE data is accurate.',
  },
  open_circuits: {
    analyst: 'Sources with issues',
    operator: 'Open circuits',
    explanation: 'Upstream API failed repeatedly; BRIEFR paused calls temporarily.',
  },
  active_locks: {
    analyst: 'Syncs in progress',
    operator: 'Active locks',
    explanation: 'A background refresh is running right now.',
  },
  circuit_reset: {
    analyst: 'Try again',
    operator: 'Reset circuit',
    explanation: 'Clears the pause and retries the source.',
  },
}

export function termLabel(key, mode = 'operator') {
  const entry = TERM_GLOSSARY[key]
  if (!entry) return key
  return mode === 'analyst' ? entry.analyst : entry.operator
}

export function termExplanation(key) {
  return TERM_GLOSSARY[key]?.explanation || ''
}

export const AUDIT_ACTION_LABELS = {
  'refresh.nvd': 'Refreshed NVD',
  'refresh.all': 'Refreshed all sources',
  'backup.run': 'Ran a backup',
  'scheduler.pause': 'Paused a job',
  'scheduler.resume': 'Resumed a job',
  'scheduler.pause_all': 'Paused all jobs',
  'scheduler.resume_all': 'Resumed all jobs',
  'scheduler.run': 'Ran a job manually',
  'watchlist.clear_snoozes': 'Cleared snoozes',
  'storage.purge.ioc_cache': 'Cleared IOC cache',
  'system.restart': 'Restarted the backend',
  'system.restart.drain': 'Drained and restarted the backend',
}

export function auditActionLabel(action) {
  return AUDIT_ACTION_LABELS[action] || action
}
