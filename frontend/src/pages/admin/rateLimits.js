// Plain-English rate-limit context for scheduler interval fields, shown
// next to the field so operators don't pick an interval that breaches an
// upstream source's limit. Only NVD publishes an actual number (see
// NVD_API_KEY help text in backend/config_schema.py) — everything else
// gets an honest "no published limit" note rather than a made-up figure.
export const RATE_LIMIT_HINTS = {
  NVD_SYNC_INTERVAL_HOURS: 'NVD allows 5 requests/30s without an API key, 50/30s with one. Hourly sync is well within either limit.',
  KEV_SYNC_INTERVAL_MINUTES: 'CISA KEV does not publish a rate limit. The catalog itself only updates a few times a day, so going below ~30 min adds load with no benefit.',
  EPSS_SYNC_INTERVAL_HOURS: 'FIRST.org does not publish a rate limit for EPSS. Scores are recomputed daily, so hourly sync is already more than enough.',
  VULNRICHMENT_SYNC_INTERVAL_HOURS: 'CISA does not publish a rate limit for the Vulnrichment GitHub repo. Hourly is a reasonable floor — it is a gap-fill sync, not time-critical.',
  CVELISTV5_SYNC_INTERVAL_MINUTES: 'GitHub does not publish a per-repo rate limit here, but unauthenticated GitHub API calls are capped at 60/hour — keep this above a few minutes.',
  INCIDENT_FEED_REFRESH_MINUTES: 'No published limit; this rebuilds an RSS snapshot, so going below a few minutes just adds load without fresher data.',
}
