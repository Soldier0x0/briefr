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

export function fmtDur(sec) {
  if (sec === null || sec === undefined) return '—'
  if (sec < 60) return `${sec.toFixed(1)} s`
  if (sec < 3600) return `${(sec / 60).toFixed(1)} min`
  return `${(sec / 3600).toFixed(1)} h`
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
