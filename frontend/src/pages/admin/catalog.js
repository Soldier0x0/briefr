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
  cpe_catalog_sync: {
    label: 'Software product catalog (CPE)',
    short: 'CPE catalog',
    operatorName: 'NVD CPE Software Catalog Sync',
    analystDescription: 'NVD CPE dictionary used for stack product autocomplete.',
    refreshButton: 'Refresh CPE catalog',
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
  otx_continuous_sync: {
    label: 'OTX continuous background sync',
    short: 'OTX continuous',
    operatorName: 'OTX Continuous Sync',
    analystDescription: 'Keeps OTX pulse and IOC data fresh throughout the day.',
    refreshButton: 'Run OTX continuous sync',
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
    label: 'Semantic search index',
    short: 'Embeddings',
    operatorName: 'Embeddings Backfill (CVE / technique / campaign)',
    analystDescription: 'Builds the hybrid search index for CVEs, MITRE techniques, and campaigns.',
    refreshButton: 'Rebuild search index',
  },
  catchup_tick: {
    label: 'Catch-up tick',
    short: 'Catch-up',
    operatorName: 'Catch-up tick',
    analystDescription: 'Kicks eligible backlog jobs while Catch-up mode is active.',
    refreshButton: 'Run catch-up tick',
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
  api_key_health_check: {
    label: 'API key health',
    short: 'Keys',
    operatorName: 'API Key Health Check',
    analystDescription: 'Lightweight ping against configured provider API keys.',
    refreshButton: 'Check API keys',
  },
  scheduled_backup: {
    label: 'Scheduled backup',
    short: 'Backup',
    operatorName: 'Scheduled Backup',
    analystDescription: 'Creates a backup archive and prunes old ones, on BACKUP_INTERVAL_HOURS.',
    refreshButton: 'Run backup',
  },
  kev_backlog_reconcile: {
    label: 'KEV detection backlog',
    short: 'KEV backlog',
    operatorName: 'Weekly KEV Detection Backlog Reconcile',
    analystDescription: 'Reconciles KEV detection backlog items on a weekly schedule.',
    refreshButton: 'Run KEV backlog reconcile',
  },
  threatfox_sync: {
    label: 'ThreatFox IOC mirror',
    short: 'ThreatFox',
    operatorName: 'ThreatFox IOC Mirror Sync',
    analystDescription: 'Mirrors Abuse.ch ThreatFox IOC feeds for correlation and watchlist matching.',
    refreshButton: 'Refresh ThreatFox',
  },
  vulncheck_kev_sync: {
    label: 'VulnCheck KEV tier',
    short: 'VulnCheck KEV',
    operatorName: 'VulnCheck KEV Tier Sync',
    analystDescription: 'Syncs supplemental KEV tier metadata from VulnCheck when configured.',
    refreshButton: 'Refresh VulnCheck KEV',
  },
  ioc_retro_match: {
    label: 'IOC watchlist retro-match',
    short: 'IOC retro',
    operatorName: 'IOC Watchlist Retro-Match',
    analystDescription: 'Matches cached IOC lookups against watchlisted CVEs on a nightly schedule.',
    refreshButton: 'Run IOC retro-match',
  },
  detection_context_sync: {
    label: 'Detection context sync',
    short: 'Detection ctx',
    operatorName: 'Detection Context Sync',
    analystDescription: 'Extracts detection-relevant context from CVE records when enabled in configuration.',
    refreshButton: 'Run detection context sync',
  },
  detection_context_llm: {
    label: 'Detection context (LLM)',
    short: 'Detection LLM',
    operatorName: 'Detection Context LLM Enrichment',
    analystDescription: 'Uses an LLM pass for detection context when DETECTION_CONTEXT_LLM_ENABLED is on.',
    refreshButton: 'Run detection LLM pass',
  },
  sigmahq_index_sync: {
    label: 'SigmaHQ index sync',
    short: 'SigmaHQ index',
    operatorName: 'SigmaHQ Detection Rule Index Sync',
    analystDescription:
      'Downloads the SigmaHQ rule archive into Postgres (DRL-1.1). Detect uses CVE-exact matches from this local index.',
    refreshButton: 'Sync SigmaHQ index',
  },
  watchlist_monitor_alerts: {
    label: 'Watchlist monitor alerts',
    short: 'Watchlist alerts',
    operatorName: 'Watchlist Monitor Alerts',
    analystDescription: 'Evaluates watchlist rules and sends configured webhook alerts.',
    refreshButton: 'Run watchlist monitor',
  },
  session_cleanup: {
    label: 'Session cleanup',
    short: 'Sessions',
    operatorName: 'Session Cleanup',
    analystDescription: 'Purges expired login sessions from the database.',
    refreshButton: 'Run session cleanup',
  },
  cache_retention_cleanup: {
    label: 'Cache retention cleanup',
    short: 'Cache cleanup',
    operatorName: 'Cache Retention Cleanup',
    analystDescription: 'Prunes aged feed cache and housekeeping rows per retention policy.',
    refreshButton: 'Run cache cleanup',
  },
  resource_metrics_sample: {
    label: 'Resource metrics sample',
    short: 'Resources',
    operatorName: 'Resource Metrics Sample',
    analystDescription: 'Samples CPU, RAM, disk I/O, and request counts for the admin Resources page.',
    refreshButton: 'Sample resources now',
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
    hint: 'Registered but gated off in configuration — enable the matching setting under API keys & config',
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

const METERING_ACTOR_LABELS = {
  job: 'Job',
  queue: 'Queue',
  user: 'User',
}

export function formatMeteringActorLabel(actorType) {
  if (!actorType) return '—'
  const key = String(actorType).toLowerCase()
  if (METERING_ACTOR_LABELS[key]) return METERING_ACTOR_LABELS[key]
  return String(actorType).replace(/\b\w/g, (c) => c.toUpperCase())
}

export const TERM_GLOSSARY = {
  api_audit_greynoise: {
    analyst: 'GreyNoise audit',
    operator: 'GreyNoise opt-in',
    explanation:
      'GreyNoise is only called when an analyst opts in during IOC Lookup (IP) or loads scanning context in a CVE drawer — not on every sync. Filter Source = greynoise to see user lookups vs background jobs.',
  },
  db_integrity: {
    analyst: 'Database health',
    operator: 'DB integrity',
    explanation: 'SQLite: PRAGMA integrity + foreign keys. PostgreSQL: pg_catalog probes (invalid indexes, unvalidated constraints, FK orphans).',
  },
  open_circuits: {
    analyst: 'Sources with issues',
    operator: 'Sources paused',
    explanation: 'Upstream API failed repeatedly; BRIEFR paused calls temporarily and will retry.',
  },
  active_locks: {
    analyst: 'Syncs in progress',
    operator: 'Jobs running',
    explanation: 'A background refresh is running right now.',
  },
  circuit_reset: {
    analyst: 'Try again',
    operator: 'Resume retries',
    explanation: 'Clears the pause and retries the source.',
  },
  heartbeat: {
    analyst: 'Status heartbeat',
    operator: 'Status heartbeat',
    explanation: 'Periodic background check that confirms a subsystem is alive and reports fresh status.',
  },
  correlation_confirmation_rate: {
    analyst: 'Confirmation rate',
    operator: 'Confirmation rate',
    explanation: 'Share of candidate CVE–intel links that passed evidence rules in the latest nightly correlation run.',
  },
  correlation_rejection_rate: {
    analyst: 'Rejection rate',
    operator: 'Rejection rate',
    explanation: 'Share of candidate links rejected by correlation guardrails.',
  },
  correlation_orphan_cve_ratio: {
    analyst: 'Orphan CVE ratio',
    operator: 'Orphan CVE ratio',
    explanation: 'CVEs with OTX pulses but no linked campaign in the nightly snapshot.',
  },
  correlation_median_evidence_age: {
    analyst: 'Median evidence age',
    operator: 'Median evidence age',
    explanation: 'Median age of OTX IOC observed/fetched timestamps supporting correlations.',
  },
}

const METERING_ACTOR_LABELS = {
  job: 'Job',
  queue: 'Queue',
  user: 'User',
}

export function formatMeteringActorLabel(actorType) {
  if (!actorType) return '—'
  const key = String(actorType).toLowerCase()
  if (METERING_ACTOR_LABELS[key]) return METERING_ACTOR_LABELS[key]
  return String(actorType).replace(/\b\w/g, (c) => c.toUpperCase())
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
  'system.restart.drain': 'Finished jobs, then restarted the backend',
}

export function auditActionLabel(action) {
  if (action.startsWith('db.explorer.browse.')) {
    const table = action.slice('db.explorer.browse.'.length)
    return `Browsed DB table ${table}`
  }
  return AUDIT_ACTION_LABELS[action] || action
}
