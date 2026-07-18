/**
 * Shared plain-language tips for domain abbreviations (UX jargon sweep).
 * Analyst surfaces use ExplainTip / ControlTooltip; admin uses HelpTip.
 */

export const DOMAIN_TERM_TIPS = {
  kev: 'CISA Known Exploited Vulnerabilities — confirmed active exploitation in the wild.',
  epss: 'Exploit Prediction Scoring System (FIRST.org) — probability of exploitation in the wild within 30 days.',
  cvss: 'Common Vulnerability Scoring System — 0–10 technical severity (impact), not exploitation likelihood.',
  poc: 'Public proof-of-concept exploit or reference available.',
  tech: 'Active MITRE ATT&CK technique filter. Click a technique below or clear to remove.',
  topTechniques:
    'Most frequent MITRE ATT&CK techniques among CVEs this week — click to filter the feed.',
  whatChanged:
    'Recent tracked CVE field changes from ingest (CVSS, EPSS, KEV, PoC).',
  topKevVendors:
    "Vendors with the most entries in CISA's Known Exploited Vulnerabilities (KEV) catalog — confirmed active exploitation, not theoretical risk.",
  topEpssMovers:
    'CVEs whose FIRST.org EPSS score rose most in the selected window — probability of exploitation in the wild within 30 days.',
  watchlistSubtab: "CVEs you've pinned from the main feed (legacy snoozes may still appear for admins).",
  watchlistState: 'pin = tracked on the watchlist; snooze = legacy hide-until-cleared entries (analyst snooze UI removed).',
  huntTechnique: 'MITRE ATT&CK technique ID for this hunt pack.',
  huntPriority: 'Relative hunt priority set when the pack was created from a CVE detail hunt.',
  isp: 'Internet Service Provider reported for this IP (AbuseIPDB).',
  asn: 'Autonomous System Number — network owner for this IP (VirusTotal).',
  usageType: 'AbuseIPDB usage type for this IP (for example data center, ISP, or hosting).',
  otx: 'AlienVault OTX — open threat-exchange pulses mentioning this indicator.',
  vt: 'VirusTotal — multi-engine malware and reputation lookup.',
  abuseipdb: 'AbuseIPDB — community reports of abusive IP activity.',
  greynoise: 'GreyNoise — internet-wide scanner and worm noise classification.',
  malwarebazaar: 'MalwareBazaar — malware sample intelligence for file hashes.',
  urlhaus: 'URLhaus — malicious URL / domain blocklist intelligence.',
}

/** Inbound API token-bucket names → operator-facing tip. */
export const INBOUND_BUCKET_TIPS = {
  ioc: 'POST /api/ioc/lookup — per-client IP pacing for external enrichment lookups.',
  refresh: 'POST /api/refresh* — manual sync / refresh triggers.',
  admin_read: 'Admin read and browse endpoints (dashboard polling).',
  wallboard: 'Wallboard display API traffic.',
  login: 'Login attempts keyed by client IP.',
  login_username:
    'Login attempts keyed by username — catches credential stuffing across many source IPs.',
  auth_refresh: 'Session / refresh-token endpoints.',
  db_explorer: 'Admin DB explorer browse queries.',
  search_token: 'Search-service token authenticated retrieval pacing.',
}

export function inboundBucketTip(name) {
  if (!name) return null
  return INBOUND_BUCKET_TIPS[name] || null
}

export function domainTermTip(key) {
  if (!key) return null
  return DOMAIN_TERM_TIPS[key] || null
}
