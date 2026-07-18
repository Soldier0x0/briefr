/** Helpers for FEED hybrid search (Embeddings E4). */

/**
 * Use /api/search/semantic when the query is the primary retrieval signal.
 * Fall back to /api/cves?search= when list filters need server-side fields
 * the hybrid payload does not carry (PoC, vendors, stack, watchlist, …).
 */
export function shouldUseHybridSearch(filters) {
  const q = (filters?.search || '').trim()
  if (!q) return false
  if (filters.poc_only || filters.kev_overdue_only || filters.watchlist_only) return false
  if (filters.vendors || filters.stack || filters.my_stack_only) return false
  if (filters.summary_only || filters.ai_context_only || filters.ai_profile_match) return false
  if (filters.technique || filters.published_on) return false
  return true
}

/** Map semantic-search hit → CVE card row shape. */
export function semanticHitToCveCard(hit) {
  if (!hit) return null
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

/** Apply severity / KEV quick filters client-side on hybrid hits. */
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
