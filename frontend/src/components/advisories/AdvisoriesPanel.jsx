import { useCallback, useEffect, useState } from 'react'
import { fetchPublications, fetchPublication } from '../../api.js'
import { notifyApiError } from '../Toast.jsx'
import { PublicationCard, SkeletonCards } from './shared.jsx'

export default function AdvisoriesPanel({ onOpenCve }) {
  const [rows, setRows] = useState([])
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [expandedId, setExpandedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    const id = setTimeout(() => setDebounced(search), 400)
    return () => clearTimeout(id)
  }, [search])

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setFailed(false)
    fetchPublications({
      limit: 50,
      mark_headlines: true,
      q: debounced || undefined,
    })
      .then(body => {
        if (cancelled) return
        setRows(Array.isArray(body?.data) ? body.data : [])
      })
      .catch(err => {
        if (!cancelled) {
          setRows([])
          setFailed(true)
          notifyApiError(err)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [debounced])

  useEffect(() => load(), [load])

  const toggleDetail = async (publicationId) => {
    if (expandedId === publicationId) {
      setExpandedId(null)
      setDetail(null)
      return
    }
    setExpandedId(publicationId)
    setDetailLoading(true)
    try {
      const body = await fetchPublication(publicationId)
      setDetail(body?.data || null)
    } catch (err) {
      setDetail(null)
      notifyApiError(err)
    } finally {
      setDetailLoading(false)
    }
  }

  return (
    <section className="cs-panel" aria-labelledby="cs-advisories-heading">
      <h2 id="cs-advisories-heading" className="cs-section-label mono">ADVISORIES</h2>
      <div className="cs-search-row">
        <input
          type="search"
          className="cs-search-input"
          placeholder="Filter advisories by title…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          aria-label="Filter advisories"
        />
      </div>
      {loading ? (
        <SkeletonCards count={4} />
      ) : failed ? (
        <p className="cs-empty mono">// Failed to load publications</p>
      ) : rows.length === 0 ? (
        <p className="cs-empty mono">
          // No structured publications yet — scheduler sync runs when{' '}
          <code>PUBLICATION_SYNC_ENABLED=1</code> on the server
        </p>
      ) : (
        <div className="cs-feed">
          {rows.map(row => (
            <div key={row.publication_id} className="cs-publication-wrap">
              {row.also_in_headlines && (
                <span className="cs-headline-badge mono" title="Same URL also appears in Headlines">
                  Also in Headlines
                </span>
              )}
              <PublicationCard row={row} onOpenCve={onOpenCve} />
              <button
                type="button"
                className="cs-detail-toggle mono"
                onClick={() => toggleDetail(row.publication_id)}
                aria-expanded={expandedId === row.publication_id}
              >
                {expandedId === row.publication_id ? 'Hide details' : 'View details'}
              </button>
              {expandedId === row.publication_id && (
                <div className="cs-publication-detail mono">
                  {detailLoading ? (
                    <p>// Loading publication detail…</p>
                  ) : detail ? (
                    <>
                      <p className="cs-detail-provenance">
                        Source: {detail.source_key} · Retrieved {detail.retrieved_at?.slice(0, 10) || '—'}
                      </p>
                      {detail.actors?.length > 0 && (
                        <p>Authors: {detail.actors.map(a => a.display_name).join(', ')}</p>
                      )}
                      {detail.entity_links?.length > 0 && (
                        <ul className="cs-detail-links">
                          {detail.entity_links.map(link => (
                            <li key={`${link.entity_type}-${link.entity_id}-${link.extractor}`}>
                              {link.entity_type}:{link.entity_id} ({link.extractor}, {link.confidence})
                            </li>
                          ))}
                        </ul>
                      )}
                    </>
                  ) : (
                    <p>// Detail unavailable</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {failed && (
        <button type="button" className="cs-retry-btn mono" onClick={load}>
          Retry
        </button>
      )}
    </section>
  )
}
