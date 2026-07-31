import { formatKevDueDate } from './kevDeadline.js'
import {
  getEnvironmentDisplay,
  getOperationalPriorityDisplay,
  getSsvcAnnotationDisplay,
} from '../scoring/riskScore.js'

export function formatTriageSnapshot(cve, risk) {
  const lines = []
  const op = getOperationalPriorityDisplay(risk)
  if (op) {
    let line = `Operational Priority: ${op.label}`
    if (op.provisional) line += ' (provisional — load My Stack for environment-aware priority)'
    if (op.escalated) line += ' · Campaign-escalated'
    lines.push(line)
  }
  if (risk?.threat?.score != null) {
    let line = `Threat Score: ${Number(risk.threat.score).toFixed(1)}/100 (${risk.threat.band || '—'})`
    if ((risk.momentumScore ?? 0) > 0.5) line += ' · Rising momentum'
    lines.push(line)
  }
  const ssvc = getSsvcAnnotationDisplay(risk)
  if (ssvc) {
    lines.push(`CISA SSVC: ${ssvc.outcome}${ssvc.path ? ` — ${ssvc.path}` : ''}`)
  }
  if (cve?.is_kev && cve?.kev_due_date) {
    const due = formatKevDueDate(cve.kev_due_date)
    if (due) lines.push(`KEV remediation due: ${due}`)
  }
  const env = getEnvironmentDisplay(risk)
  if (env && env.tier && env.tier !== 'UNKNOWN') {
    lines.push(`Environment relevance: ${env.label}${env.evidence ? ` — ${env.evidence}` : ''}`)
  }
  return lines.join('\n')
}

export function formatCapecSection(cve) {
  const ids = Array.isArray(cve?.capec_ids) ? cve.capec_ids.filter(Boolean) : []
  if (!ids.length) return ''
  return ids.map(id => {
    const m = String(id).trim().match(/^(?:CAPEC-)?(\d+)$/i)
    const label = m ? `CAPEC-${m[1]}` : String(id).trim().toUpperCase()
    const href = m ? `https://capec.mitre.org/data/definitions/${m[1]}.html` : ''
    return href ? `${label}: ${href}` : label
  }).join('\n')
}

export function formatRelatedSection(related = [], relatedNews = [], relatedMethod = '') {
  const parts = []
  if (related.length) {
    const lane = relatedMethod === 'embeddings' ? 'Similar description' : 'Same product family'
    parts.push(`${lane}:`)
    related.slice(0, 5).forEach(item => {
      const sev = (item.severity || '').toUpperCase()
      const cvss = item.cvss_score != null ? ` CVSS ${Number(item.cvss_score).toFixed(1)}` : ''
      parts.push(`• ${item.cve_id}${sev ? ` (${sev}${cvss})` : ''}`)
    })
  }
  if (relatedNews.length) {
    parts.push('In incidents & news:')
    relatedNews.slice(0, 5).forEach(item => {
      parts.push(`• ${item.source || 'News'}: ${item.title || 'Untitled'}`)
    })
  }
  return parts.join('\n')
}

export function formatDetectionOverview(detection) {
  if (!detection) return ''
  const parts = []
  const sigmaRules = detection.sigma_rules || []
  const elasticRules = detection.elastic_rules || []

  if (sigmaRules.length) {
    parts.push('Community Sigma rules:')
    sigmaRules.slice(0, 6).forEach(rule => {
      const title = rule.title || rule.name || rule.path?.split('/').pop() || 'Sigma rule'
      const basis = rule.match_basis ? ` [${rule.match_basis}]` : ''
      parts.push(`• ${title}${basis}`)
    })
  }
  if (elasticRules.length) {
    parts.push('Community Elastic rules:')
    elasticRules.slice(0, 4).forEach(rule => {
      parts.push(`• ${rule.name || 'Elastic rule'}`)
    })
  }

  const nucleiUrls = detection.evidence?.observables?.nuclei_urls || []
  if (nucleiUrls.length) {
    parts.push('Nuclei templates:')
    nucleiUrls.slice(0, 4).forEach(url => parts.push(`• ${url}`))
  }

  const yaraRules = detection.yara_rules || []
  if (yaraRules.length) {
    parts.push(`YARA hunt templates: ${yaraRules.length} generated from OTX file hashes (experimental).`)
  }

  const logPatterns = detection.siem_queries?.log_patterns || []
  if (logPatterns.length) {
    parts.push('Log patterns to monitor:')
    logPatterns.forEach(p => parts.push(`• ${p}`))
  }

  if (!parts.length) {
    return 'No community detection rules or hunt starters matched for this CVE.'
  }
  return parts.join('\n')
}

export function pickCommunitySigmaYaml(detection) {
  const rules = detection?.sigma_rules || []
  const match = rules.find(r => r.content)
  return match?.content || ''
}

export function pickHuntStarterYaml(detection) {
  return detection?.generated_sigma || ''
}

export function pickFirstYaraRule(detection) {
  const rules = detection?.yara_rules || []
  const match = rules.find(r => r.yara || r.content)
  return match?.yara || match?.content || ''
}

export function formatReferencesSection(cve) {
  const urls = Array.isArray(cve?.source_urls) ? cve.source_urls.filter(Boolean) : []
  if (!urls.length) return 'No additional reference URLs stored.'
  return urls.map((url, i) => `${i + 1}. ${url}`).join('\n')
}
