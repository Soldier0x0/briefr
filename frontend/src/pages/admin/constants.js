export const NAV = [
  { section: 'OVERVIEW', items: [{ id: 'overview', label: 'System health', badgeKey: 'jobs_with_errors_count' }] },
  { section: 'DATA', items: [
    { id: 'backups', label: 'Backups' },
    { id: 'storage', label: 'Storage' },
    { id: 'watchlist', label: 'Watchlist & cache' },
  ]},
  { section: 'CONFIGURATION', items: [
    { id: 'apikeys', label: 'API keys & config' },
    { id: 'scheduler', label: 'Scheduler' },
    { id: 'webhooks', label: 'Webhooks' },
    { id: 'security', label: 'Security', badgeKey: 'failed_auth_last_24h' },
  ]},
  { section: 'FEEDS', items: [
    { id: 'feedhealth', label: 'Feed health', badgeKey: 'open_circuit_count' },
    { id: 'ingestlog', label: 'Ingest log', badgeKey: 'ingest_error_count' },
  ]},
  { section: 'AUDIT', items: [
    { id: 'auditlog', label: 'Audit log' },
  ]},
  { section: 'COMING SOON', items: [
    { id: 'coming-login', label: 'App login & sessions', locked: true, tooltip: 'Ships in V1.4 / T3-S0' },
    { id: 'coming-users', label: 'Multi-user management', locked: true, tooltip: 'Ships in V2.0' },
    { id: 'coming-postgres', label: 'Postgres migration', locked: true, tooltip: 'Ships in V2.0' },
    { id: 'coming-ratelimit', label: 'Rate limit dashboard', locked: true, tooltip: 'Ships in V1.4' },
  ]},
]

export const MANUAL_PIPELINES = [
  { id: 'nvd_incremental_sync', label: 'NVD only' },
  { id: 'kev_metadata_sync', label: 'KEV only' },
  { id: 'epss_score_sync', label: 'EPSS only' },
  { id: 'weekly_mitre_refresh', label: 'MITRE + ATLAS' },
  { id: 'incident_feed_refresh', label: 'Incident RSS' },
  { id: 'nightly_correlation', label: 'Correlation' },
]

export const AUDIT_PREFIXES = ['backup', 'refresh', 'scheduler', 'storage', 'config', 'system', 'webhook', 'watchlist', 'feed', 'diagnostics']

export const COMING_SOON_INFO = {
  'coming-login': {
    title: 'App login & sessions',
    message: 'Ships in V1.4 (T3-S0). Adds built-in auth, httpOnly session cookies, login page, and audit_log.actor population.',
  },
  'coming-users': {
    title: 'Multi-user management',
    message: 'Ships in V2.0. The users table schema is already designed (id, email, password_hash, role, is_active, created_at) and will be activated when multi-user is enabled.',
  },
  'coming-postgres': {
    title: 'Postgres migration',
    message: 'Ships in V2.0. To migrate: set DATABASE_URL to a postgres:// connection string, set NVD_DAYS_BACK=3650 and restart. The scheduler will refill from NVD. Keep SQLite as fallback until Postgres is confirmed stable.',
  },
  'coming-ratelimit': {
    title: 'Rate limit dashboard',
    message: 'Ships in V1.4. Will show per-IP bucket levels, top consumers, and allow per-IP block/allowlist.',
  },
}
