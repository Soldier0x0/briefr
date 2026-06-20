import { fetchCaseStudyFeed } from '../api.js'

const CAMPAIGN_RE = /\b(APT\d{1,2}|threat actor|campaign|nation[- ]state|ransomware group)\b/i
const FEED_CACHE_MS = 5 * 60 * 1000

let feedCache = null
let feedCacheAt = 0

export async function loadCaseStudyFeed({ force = false } = {}) {
  if (!force && feedCache && Date.now() - feedCacheAt < FEED_CACHE_MS) {
    return feedCache
  }

  const res = await fetchCaseStudyFeed(80)
  const result = {
    cards: res?.data || [],
    errors: res?.errors || [],
    meta: res?.meta || null,
  }
  // A warming response means the server snapshot is still being built —
  // do not pin the empty result for FEED_CACHE_MS.
  if (!res?.meta?.warming) {
    feedCache = result
    feedCacheAt = Date.now()
  }
  return result
}

export function clearCaseStudyFeedCache() {
  feedCache = null
  feedCacheAt = 0
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
