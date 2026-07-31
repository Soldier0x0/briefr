import { formatKevDueDate } from './kevDeadline.js'
import {
  getEnvironmentDisplay,
  getOperationalPriorityDisplay,
  getSsvcAnnotationDisplay,
} from '../scoring/riskScore.js'

const SIGMA_MATCH_RANK = {
  cve_exact: 0,
  cve_search: 1,
  technique_related: 2,
}

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

export function formatSigmaAttribution(rule) {
  const parts = []
  if (rule.attribution) {
    parts.push(rule.attribution)
  } else {
    const author = String(rule.author || '').trim()
    parts.push(author ? `SigmaHQ · ${author}` : 'SigmaHQ (Detection Rule License 1.1)')
  }
  if (rule.license) parts.push(`License: ${rule.license}`)
  if (rule.match_basis) parts.push(`Match: ${rule.match_basis}`)
  if (rule.html_url) parts.push(`Source: ${rule.html_url}`)
  return parts.join(' · ')
}

export function formatElasticAttribution(rule) {
  const parts = ['Elastic Detection Rules (elastic/detection-rules)']
  if (rule.language) parts.push(`Language: ${rule.language}`)
  if (rule.html_url) parts.push(`Source: ${rule.html_url}`)
  return parts.join(' · ')
}

/** Official SigmaHQ rules with fetched YAML — ranked CVE-exact first. */
export function collectOfficialSigmaRulesForPdf(detection, { maxRules = 2 } = {}) {
  const rules = (detection?.sigma_rules || []).filter(rule => {
    if (!rule?.content) return false
    const source = String(rule.source || '').toLowerCase()
    return source.includes('sigma') || Boolean(rule.path)
  })

  return [...rules]
    .sort((a, b) => {
      const rankA = SIGMA_MATCH_RANK[a.match_basis] ?? 9
      const rankB = SIGMA_MATCH_RANK[b.match_basis] ?? 9
      if (rankA !== rankB) return rankA - rankB
      return String(a.title || a.path || '').localeCompare(String(b.title || b.path || ''))
    })
    .slice(0, maxRules)
    .map(rule => ({
      kind: 'sigma',
      title: rule.title || rule.path?.split('/').pop()?.replace('.yml', '') || 'Sigma rule',
      content: rule.content,
      attribution: formatSigmaAttribution(rule),
      sourceUrl: rule.html_url || rule.download_url || '',
    }))
}

/** Official Elastic community rules (metadata + source links; body not stored in API). */
export function collectOfficialElasticRulesForPdf(detection, { maxRules = 4 } = {}) {
  return (detection?.elastic_rules || [])
    .slice(0, maxRules)
    .map(rule => ({
      kind: 'elastic',
      title: rule.name || rule.path?.split('/').pop() || 'Elastic detection rule',
      attribution: formatElasticAttribution(rule),
      sourceUrl: rule.html_url || rule.download_url || '',
    }))
}

export function formatDetectionOverview(detection) {
  if (!detection) return ''

  const parts = []
  const sigmaRules = collectOfficialSigmaRulesForPdf(detection)
  const elasticRules = collectOfficialElasticRulesForPdf(detection)

  if (sigmaRules.length) {
    parts.push('Official SigmaHQ rules (YAML included below when fetched):')
    sigmaRules.forEach(rule => {
      parts.push(`• ${rule.title} — ${rule.attribution}`)
    })
  }

  if (elasticRules.length) {
    parts.push('Official Elastic detection rules (view/download from source):')
    elasticRules.forEach(rule => {
      parts.push(`• ${rule.title} — ${rule.attribution}`)
    })
  }

  const nucleiUrls = detection.evidence?.observables?.nuclei_urls || []
  if (nucleiUrls.length) {
    parts.push('Official Nuclei templates (ProjectDiscovery):')
    nucleiUrls.slice(0, 4).forEach(url => parts.push(`• ${url}`))
  }

  if (!parts.length) {
    return 'No official community detection rules (SigmaHQ / Elastic) matched for this CVE. BRIEFR-generated hunt starters are omitted from PDF exports.'
  }

  return parts.join('\n')
}

export function formatReferencesSection(cve) {
  const urls = Array.isArray(cve?.source_urls) ? cve.source_urls.filter(Boolean) : []
  if (!urls.length) return 'No additional reference URLs stored.'
  return urls.map((url, i) => `${i + 1}. ${url}`).join('\n')
}
