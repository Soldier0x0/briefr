import { getDisplayPrefs } from '../../utils/displayPrefs.js'

export function fmtAge(seconds) {
  if (seconds === null || seconds === undefined) return '—'
  const s = Math.round(seconds)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return `${Math.round(s / 86400)}d ago`
}

export function fmtBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0; let val = bytes
  while (val >= 1024 && i < units.length - 1) { val /= 1024; i++ }
  return `${val.toFixed(1)} ${units[i]}`
}

/**
 * Scale for plotting byte series so Y-axis ticks and tooltip values share
 * one linear display unit. Plotting raw bytes makes Recharts pick decimal
 * "nice" ticks (25e6, 50e6, …) that fmtBytes turns into awkward MB labels
 * (23.8, 47.7, …), so a 50.3 MB point sits almost on the "47.7 MB" grid line.
 */
export function bytesChartScale(valuesBytes) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const nums = (valuesBytes || [])
    .map((v) => Number(v))
    .filter((n) => Number.isFinite(n) && n >= 0)
  const maxBytes = nums.length ? Math.max(...nums) : 0
  let unitIndex = 0
  let divisor = 1
  const peak = maxBytes > 0 ? maxBytes : 1
  while (peak / divisor >= 1024 && unitIndex < units.length - 1) {
    divisor *= 1024
    unitIndex += 1
  }
  const unit = units[unitIndex]
  const toDisplay = (bytes) => {
    const n = Number(bytes)
    if (!Number.isFinite(n) || n <= 0) return 0
    return n / divisor
  }
  const format = (displayVal) => {
    const n = Number(displayVal)
    if (!Number.isFinite(n)) return '—'
    return `${n.toFixed(1)} ${unit}`
  }
  const maxDisplay = toDisplay(maxBytes)
  return {
    unit,
    divisor,
    toDisplay,
    format,
    domainMax: niceCeil(maxDisplay),
  }
}

/** @param {number} n */
export function niceCeil(n) {
  if (!Number.isFinite(n) || n <= 0) return 1
  const exp = Math.floor(Math.log10(n))
  const mag = 10 ** exp
  const frac = n / mag
  // Float noise can push an exact 1/2/5 boundary slightly above the tier
  // (e.g. 5 → 5.000000000000001), which would incorrectly jump to the next
  // nice number and double the chart domain.
  const eps = 1e-12
  let niceFrac
  if (frac <= 1 + eps) niceFrac = 1
  else if (frac <= 2 + eps) niceFrac = 2
  else if (frac <= 5 + eps) niceFrac = 5
  else niceFrac = 10
  return niceFrac * mag
}

export function fmtDur(sec) {
  if (sec === null || sec === undefined) return '—'
  if (sec < 60) return `${sec.toFixed(1)} s`
  if (sec < 3600) return `${(sec / 60).toFixed(1)} min`
  return `${(sec / 3600).toFixed(1)} h`
}

/**
 * Scale for plotting duration series in one unit (s / min / h).
 * Raw seconds + fmtDur on Recharts nice ticks mixes units on one axis
 * (e.g. "45.0 s" next to "1.5 min"), the same class of mismatch as
 * raw bytes + fmtBytes.
 */
export function durationChartScale(valuesSeconds) {
  const nums = (valuesSeconds || [])
    .map((v) => Number(v))
    .filter((n) => Number.isFinite(n) && n >= 0)
  const maxSec = nums.length ? Math.max(...nums) : 0
  let unit = 's'
  let divisor = 1
  if (maxSec >= 3600) {
    unit = 'h'
    divisor = 3600
  } else if (maxSec >= 60) {
    unit = 'min'
    divisor = 60
  }
  const toDisplay = (seconds) => {
    const n = Number(seconds)
    if (!Number.isFinite(n) || n <= 0) return 0
    return n / divisor
  }
  const format = (displayVal) => {
    const n = Number(displayVal)
    if (!Number.isFinite(n)) return '—'
    return `${n.toFixed(1)} ${unit}`
  }
  return {
    unit,
    divisor,
    toDisplay,
    format,
    domainMax: niceCeil(toDisplay(maxSec)),
  }
}

export function fmtIso(iso) {
  if (!iso) return '—'
  if (getDisplayPrefs().utcTime) return fmtIsoMono(iso)
  try { return new Date(iso).toLocaleString() } catch { return iso }
}

export function fmtIsoMono(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toISOString().replace('T', ' ').replace('Z', ' UTC') } catch { return iso }
}

export function ageColor(seconds, greenMax, amberMax) {
  if (seconds === null || seconds === undefined) return ''
  if (seconds <= greenMax) return 'color-green'
  if (seconds <= amberMax) return 'color-amber'
  return 'color-red'
}

export function diskPct(partition) {
  if (!partition || !partition.total || partition.total === 0) return 0
  return Math.round((partition.used / partition.total) * 100)
}

export function diskBarColor(pct) {
  if (pct < 70) return 'green'
  if (pct < 90) return 'amber'
  return 'red'
}

export const SOURCE_DISPLAY = {
  nvd: 'NVD API', kev: 'CISA KEV', epss: 'FIRST EPSS',
  mitre_attack: 'MITRE ATT&CK', mitre_atlas: 'MITRE ATLAS',
  otx: 'OTX', cvelistv5: 'CVE List V5', vulnrichment: 'CISA Vulnrichment',
  embeddings: 'CVE Embeddings', llm: 'Groq Product Extraction',
  exploitdb: 'ExploitDB', metasploit: 'Metasploit',
  nuclei: 'Nuclei Templates', poc_github: 'PoC-in-GitHub',
  threatfox: 'ThreatFox', vulncheck: 'VulnCheck',
  'webhook.discord': 'Discord Webhook', 'webhook.telegram': 'Telegram Webhook',
}

export function sourceLabel(key) { return SOURCE_DISPLAY[key] || key }
