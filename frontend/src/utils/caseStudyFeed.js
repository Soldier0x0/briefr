import { fetchAtlasCaseStudies } from '../api.js'
import {
  ATLAS_YAML_FALLBACK,
  CASE_STUDY_SOURCES,
  RSS_PROXY_BASE,
} from '../config/caseStudySources.js'

const TECHNIQUE_RE = /\b(T\d{4}(?:\.\d{3})?|AML\.T\d{4}(?:\.\d{3})?)\b/gi

const TAG_HINTS = [
  'Okta', 'nginx', 'Kubernetes', 'TensorFlow', 'PyTorch', 'AWS', 'Azure',
  'Google', 'Microsoft', 'Cisco', 'Fortinet', 'Palo Alto', 'VMware',
  'Exchange', 'Active Directory', 'Linux', 'Windows', 'Docker', 'Jenkins',
  'GitHub', 'GitLab', 'CrowdStrike', 'SentinelOne', 'Splunk', 'Elastic',
  'MongoDB', 'PostgreSQL', 'Redis', 'Apache', 'IIS', 'OpenSSL', 'Java',
  'Python', 'Node.js', 'React', 'Spring', 'Confluence', 'Jira', 'Citrix',
]

const CAMPAIGN_RE = /\b(APT\d{1,2}|threat actor|campaign|nation[- ]state|ransomware group)\b/i

function stripHtml(text) {
  if (!text) return ''
  const doc = new DOMParser().parseFromString(text, 'text/html')
  return (doc.body.textContent || '').replace(/\s+/g, ' ').trim()
}

function truncateSentences(text, maxLen = 280) {
  const t = stripHtml(text)
  if (t.length <= maxLen) return t
  return `${t.slice(0, maxLen - 1).trim()}…`
}

function parseRssDate(raw) {
  if (!raw) return null
  const d = new Date(raw)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}

function extractMeta(title, description) {
  const text = `${title} ${description}`
  const techniques = [...new Set((text.match(TECHNIQUE_RE) || []).map(t => t.toUpperCase()))]
  const tags = []
  const lower = text.toLowerCase()
  for (const hint of TAG_HINTS) {
    if (lower.includes(hint.toLowerCase())) tags.push(hint)
  }
  return { techniques, tags }
}

function parseRssXml(xmlText, source) {
  const doc = new DOMParser().parseFromString(xmlText, 'text/xml')
  if (doc.querySelector('parsererror')) {
    throw new Error('Invalid RSS XML')
  }

  const nodes = [
    ...doc.querySelectorAll('item'),
    ...doc.querySelectorAll('entry'),
  ]

  return nodes.map(node => {
    const title = stripHtml(
      node.querySelector('title')?.textContent || '',
    )
    const linkEl =
      node.querySelector('link[href]') ||
      node.querySelector('link') ||
      node.querySelector('guid')
    let url = linkEl?.getAttribute?.('href') || linkEl?.textContent || ''
    url = url.trim()
    const description = stripHtml(
      node.querySelector('description')?.textContent ||
      node.querySelector('content\\:encoded')?.textContent ||
      node.querySelector('summary')?.textContent ||
      node.querySelector('content')?.textContent ||
      '',
    )
    const publishedAt =
      parseRssDate(node.querySelector('pubDate')?.textContent) ||
      parseRssDate(node.querySelector('published')?.textContent) ||
      parseRssDate(node.querySelector('updated')?.textContent) ||
      new Date().toISOString()
    const { techniques, tags } = extractMeta(title, description)

    return {
      id: url || `${source.id}:${title}`,
      source: source.label,
      sourceId: source.id,
      title,
      description: truncateSentences(description || title),
      publishedAt,
      url,
      techniques,
      tags,
      kind: 'news',
    }
  }).filter(card => card.title && card.url)
}

// SOURCE: https://api.allorigins.win/raw?url=<RSS_URL>
export async function fetchRssSource(source) {
  const proxyUrl = `${RSS_PROXY_BASE}${encodeURIComponent(source.url)}`
  const res = await fetch(proxyUrl)
  if (!res.ok) {
    throw new Error(`${source.label}: HTTP ${res.status}`)
  }
  const xml = await res.text()
  return parseRssXml(xml, source)
}

function normalizeAtlasStudy(study) {
  const techniques = (study.techniques || study.technique_ids || []).map(t =>
    String(t).toUpperCase(),
  )
  const techniqueDetails = study.technique_details || []
  for (const td of techniqueDetails) {
    const tid = td.technique_id || td.id
    if (tid) techniques.push(String(tid).toUpperCase())
  }
  const uniqueTech = [...new Set(techniques)]
  const summary = truncateSentences(study.summary || study.description || study.name || '')
  const { tags } = extractMeta(study.name || '', summary)
  if (study.target) tags.push(study.target)

  return {
    id: study.study_id || study.id || study.name,
    source: 'MITRE ATLAS',
    sourceId: 'atlas',
    title: study.name || 'ATLAS case study',
    description: summary,
    publishedAt: study.date || study.incident_date || study.published || new Date().toISOString(),
    url: study.url || `https://atlas.mitre.org/studies/${study.study_id || study.id || ''}`,
    techniques: uniqueTech,
    tags: [...new Set(tags.filter(Boolean))],
    actor: study.actor || study.incident_group || '',
    target: study.target || '',
    kind: 'atlas',
  }
}

// SOURCE: BRIEFR /api/atlas/casestudies (MITRE ATLAS corpus)
async function fetchAtlasCards() {
  try {
    const res = await fetchAtlasCaseStudies(80)
    const rows = res?.data || []
    if (rows.length) return rows.map(normalizeAtlasStudy)
  } catch {
    /* fall through to YAML */
  }

  // SOURCE: https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/ATLAS.yaml
  const yamlUrl = ATLAS_YAML_FALLBACK
  const proxyUrl = `${RSS_PROXY_BASE}${encodeURIComponent(yamlUrl)}`
  const res = await fetch(proxyUrl)
  if (!res.ok) throw new Error(`MITRE ATLAS: HTTP ${res.status}`)
  const text = await res.text()
  return parseAtlasYamlCaseStudies(text)
}

function parseAtlasYamlCaseStudies(yamlText) {
  const studies = []
  const blocks = yamlText.split(/\r?\n  - object-type: case-study/)
  for (const block of blocks.slice(1)) {
    const idMatch = block.match(/\r?\n    id:\s*(\S+)/)
    const nameMatch = block.match(/\r?\n    name:\s*([^\r\n]+)/)
    const summaryMatch = block.match(/\r?\n    summary:\s*([^\r\n]+)/)
    const dateMatch = block.match(/\r?\n    date:\s*['"]?([^'"\r\n]+)/)
    const targetMatch = block.match(/\r?\n    target:\s*([^\r\n]+)/)
    const studyId = idMatch?.[1] || ''
    studies.push(
      normalizeAtlasStudy({
        study_id: studyId,
        name: (nameMatch?.[1] || studyId).replace(/^['"]|['"]$/g, ''),
        summary: summaryMatch?.[1]?.replace(/^['"]|['"]$/g, '') || '',
        date: dateMatch?.[1] || '',
        target: targetMatch?.[1]?.replace(/^['"]|['"]$/g, '') || '',
        url: studyId ? `https://atlas.mitre.org/studies/${studyId}` : 'https://atlas.mitre.org/',
        techniques: [...block.matchAll(/AML\.T\d{4}(?:\.\d{3})?/gi)].map(m => m[0].toUpperCase()),
      }),
    )
  }
  return studies
}

export async function loadCaseStudyFeed() {
  const rssSources = CASE_STUDY_SOURCES.filter(s => s.type === 'rss')
  const cards = []
  const errors = []

  await Promise.all(
    rssSources.map(async source => {
      try {
        const items = await fetchRssSource(source)
        cards.push(...items)
      } catch (err) {
        errors.push({ source: source.label, message: err.message || 'Failed to load' })
      }
    }),
  )

  try {
    const atlasCards = await fetchAtlasCards()
    cards.push(...atlasCards)
  } catch (err) {
    errors.push({ source: 'MITRE ATLAS', message: err.message || 'Failed to load' })
  }

  cards.sort((a, b) => new Date(b.publishedAt) - new Date(a.publishedAt))
  return { cards, errors }
}

export function filterCaseStudyCards(cards, query) {
  const q = query.trim().toLowerCase()
  if (!q) return cards
  return cards.filter(card => {
    const hay = [
      card.title,
      card.description,
      card.source,
      card.actor,
      card.target,
      ...(card.tags || []),
      ...(card.techniques || []),
    ]
      .join(' ')
      .toLowerCase()
    return hay.includes(q)
  })
}

export function isCampaignArticle(card) {
  if (card.kind !== 'news') return false
  const text = `${card.title} ${card.description}`
  return CAMPAIGN_RE.test(text)
}

export function relativeDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const diff = Date.now() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 48) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 14) return `${days}d ago`
  return d.toISOString().slice(0, 10)
}

export function highlightParts(text, query) {
  if (!text || !query.trim()) return [{ text, match: false }]
  const q = query.trim()
  const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return text.split(re).filter(Boolean).map(part => ({
    text: part,
    match: part.toLowerCase() === q.toLowerCase(),
  }))
}
