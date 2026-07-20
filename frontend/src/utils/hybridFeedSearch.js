/** Helpers for FEED hybrid search (Embeddings E4). */

/**
 * Use /api/search/semantic when the query is the primary retrieval signal.
 * Fall back to /api/cves?search= when list filters need fields hybrid cannot
 * express yet (PoC, vendors, watchlist, technique day, …).
 *
 * E7: stack / My Stack stay on hybrid — API accepts ``stack`` and filters CVE hits.
 * Severity / KEV chips also stay on hybrid (API + client filter).
 */
export function shouldUseHybridSearch(filters) {
  const q = (filters?.search || '').trim()
  if (!q) return false
  if (filters?.poc_only || filters?.kev_overdue_only || filters?.watchlist_only) return false
  if (filters?.vendors) return false
  if (filters?.summary_only || filters?.ai_context_only || filters?.ai_profile_match) return false
  if (filters?.technique || filters?.published_on) return false
  return true
}

/** Map semantic-search hit → CVE card row shape. */
export function semanticHitToCveCard(hit) {
  if (!hit) return null
  const entityType = String(hit.entity_type || 'cve').toLowerCase()
  if (entityType !== 'cve') return null
  const cveId = hit.cve_id || hit.entity_id
  if (!cveId) return null
  return {
    cve_id: cveId,
    description: hit.description || '',
    summary: hit.summary || '',
    cvss_score: hit.cvss_score ?? null,
    severity: hit.severity || null,
    published: hit.published || null,
    epss_score: hit.epss_score ?? null,
    is_kev: Boolean(hit.is_kev),
    similarity: hit.similarity,
    match_reasons: hit.match_reasons || [],
    score: hit.score,
  }
}

/** Map semantic-search hit → technique row shape. */
export function semanticHitToTechniqueCard(hit) {
  if (!hit) return null
  const techniqueId = hit.technique_id || hit.entity_id
  if (!techniqueId) return null
  return {
    entity_type: 'technique',
    technique_id: techniqueId,
    name: hit.name || techniqueId,
    description: hit.description || '',
    tactic: hit.tactic || '',
    url: hit.url || '',
    similarity: hit.similarity,
    match_reasons: hit.match_reasons || [],
    score: hit.score,
  }
}

/** Map semantic-search hit → campaign row shape. */
export function semanticHitToCampaignCard(hit) {
  if (!hit) return null
  const campaignId = hit.campaign_id || hit.entity_id
  if (!campaignId) return null
  return {
    entity_type: 'campaign',
    campaign_id: campaignId,
    label: hit.label || campaignId,
    adversary: hit.adversary || '',
    lifecycle: hit.lifecycle || '',
    member_count: hit.member_count ?? 0,
    confidence: hit.confidence || '',
    similarity: hit.similarity,
    match_reasons: hit.match_reasons || [],
    score: hit.score,
  }
}

/** Split hybrid API hits by entity type (CVE / technique / campaign). */
export function partitionHybridHits(hits) {
  const cves = []
  const techniques = []
  const campaigns = []
  for (const hit of hits || []) {
    const entityType = String(hit?.entity_type || 'cve').toLowerCase()
    if (entityType === 'technique') {
      techniques.push(hit)
    } else if (entityType === 'campaign') {
      campaigns.push(hit)
    } else {
      cves.push(hit)
    }
  }
  return { cves, techniques, campaigns }
}

/** Partition hybrid hits and map each section to feed row shapes. */
export function processHybridSearchResults(hits, filters) {
  const { cves, techniques, campaigns } = partitionHybridHits(hits)
  return {
    cves: filterHybridHits(cves, filters),
    techniques: techniques.map(semanticHitToTechniqueCard).filter(Boolean),
    campaigns: campaigns.map(semanticHitToCampaignCard).filter(Boolean),
  }
}

/** Apply severity / KEV quick filters client-side on hybrid CVE hits. */
export function filterHybridHits(hits, filters) {
  let rows = hits.map(semanticHitToCveCard).filter(Boolean)
  if (filters?.severity) {
    const sev = String(filters.severity).toUpperCase()
    rows = rows.filter((r) => String(r.severity || '').toUpperCase() === sev)
  }
  if (filters?.kev_only) {
    rows = rows.filter((r) => r.is_kev)
  }
  return rows
}

/** Quiet status copy when semantic degrades (design §9). */
export function hybridSearchStatusLabel(meta) {
  if (!meta) return ''
  const method = meta.method || ''
  if (method === 'keyword_fallback') {
    return 'Keyword matches (semantic unavailable)'
  }
  if (method === 'keyword_first') {
    return 'CVE-ID match'
  }
  if (method === 'hybrid') {
    return 'Hybrid search'
  }
  if (method === 'semantic') {
    return 'Semantic search'
  }
  if (method === 'keyword') {
    return 'Keyword search'
  }
  return ''
}
