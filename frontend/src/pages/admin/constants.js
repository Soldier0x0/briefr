export const NAV = [
  { section: 'OVERVIEW', items: [{ id: 'overview', label: 'System health', icon: 'Activity', badgeKey: 'jobs_with_errors_count' }] },
  { section: 'DATA', items: [
    { id: 'backups', label: 'Backups', icon: 'Archive' },
    { id: 'storage', label: 'Storage', icon: 'HardDrive' },
    { id: 'resources', label: 'Resources', icon: 'Cpu' },
    { id: 'database', label: 'Database', icon: 'Database' },
    { id: 'watchlist', label: 'Watchlist & cache', icon: 'Bookmark' },
  ]},
  { section: 'CONFIGURATION', items: [
    { id: 'apikeys', label: 'API keys & config', icon: 'KeyRound' },
    { id: 'scheduler', label: 'Scheduler', icon: 'Clock' },
    { id: 'webhooks', label: 'Webhooks', icon: 'Webhook' },
    { id: 'aiops', label: 'AI operations', icon: 'Sparkles' },
    { id: 'security', label: 'Security', icon: 'ShieldAlert', badgeKey: 'failed_auth_last_24h' },
    { id: 'ratelimit', label: 'Inbound limits', icon: 'Gauge' },
  ]},
  { section: 'SECURITY POSTURE', items: [
    { id: 'securityposture', label: 'Security posture', icon: 'Shield' },
  ]},
  { section: 'OBSERVABILITY', items: [
    { id: 'feedhealth', label: 'Feed health', icon: 'HeartPulse', badgeKey: 'open_circuit_count' },
    { id: 'ingestlog', label: 'Application logs', icon: 'ScrollText', badgeKey: 'ingest_error_count' },
  ]},
  { section: 'AUDIT', items: [
    { id: 'auditlog', label: 'Audit log', icon: 'ClipboardList' },
  ]},
  { section: 'PREFERENCES', items: [
    { id: 'display', label: 'Display', icon: 'Settings2' },
  ]},
]

export const ANALYST_NAV = [
  { section: 'INTEL', items: [
    { id: 'overview', label: 'Intel status', icon: 'Activity', badgeKey: 'jobs_with_errors_count' },
    { id: 'feedhealth', label: 'Source status', icon: 'HeartPulse', badgeKey: 'open_circuit_count' },
    { id: 'alerts', label: 'Alert channels', icon: 'BellRing' },
    { id: 'securityposture', label: 'Security posture', icon: 'Shield' },
  ]},
  { section: 'YOUR DATA', items: [
    { id: 'watchlist', label: 'Pinned CVEs', icon: 'Bookmark' },
  ]},
  { section: 'PREFERENCES', items: [
    { id: 'display', label: 'Display', icon: 'Settings2' },
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

export const AUDIT_PREFIXES = ['backup', 'refresh', 'scheduler', 'storage', 'config', 'system', 'webhook', 'watchlist', 'feed', 'diagnostics', 'db']

export const COMING_SOON_INFO = {
  'coming-login': {
    title: 'App login & sessions',
    message: 'Ships in V1.4 (T3-S0). Adds built-in auth, httpOnly session cookies, login page, and audit_log.actor population.',
  },
  'coming-users': {
    title: 'Multi-user management',
    message: 'Ships in V2.0. The users table schema is already designed (id, username, password_hash, role, is_active, created_at) and will be activated when multi-user is enabled.',
  },
  'coming-ratelimit': {
    title: 'Rate limit dashboard',
    message: 'Ships in V1.4. Will show rate-limit usage statistics.',
  },
}

export const ADMIN_MODE_LABELS = {
  analyst: 'Analyst view',
  operator: 'Operator view',
}

/** Resolve sidebar section + page label for breadcrumbs (E8-2). */
export function resolveAdminPage(pageId, mode = 'operator') {
  const nav = mode === 'analyst' ? ANALYST_NAV : NAV
  for (const section of nav) {
    const item = section.items.find(i => i.id === pageId)
    if (item) {
      return { section: section.section, label: item.label, pageId: item.id }
    }
  }
  const coming = COMING_SOON_INFO[pageId]
  if (coming) {
    return { section: 'COMING SOON', label: coming.title, pageId }
  }
  return { section: null, label: pageId, pageId }
}
