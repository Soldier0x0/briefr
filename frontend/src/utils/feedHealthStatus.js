/** Feed pipeline status for the main-app header dot (from GET /api/health). */

export function feedHealthLevel(feedHealth) {
  if (!feedHealth) return 'unknown'
  if (feedHealth.refresh_in_progress) return 'syncing'
  if ((feedHealth.cve_count ?? 0) >= 10) return 'live'
  return 'idle'
}

export function feedHealthLabel(level) {
  switch (level) {
    case 'live': return 'CVE feeds active'
    case 'syncing': return 'Ingest running'
    case 'idle': return 'Building CVE database'
    default: return 'Checking feed status'
  }
}
