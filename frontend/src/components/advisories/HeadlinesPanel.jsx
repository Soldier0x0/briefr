import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  filterCaseStudyCards,
  isCampaignArticle,
  loadCaseStudyFeed,
} from '../../utils/caseStudyFeed.js'
import { notifyApiError } from '../Toast.jsx'
import { ingestLogUrl } from '../../utils/adminLinks.js'
import { FeedCard, SkeletonCards } from './shared.jsx'

export default function HeadlinesPanel({
  initialSearch = '',
  onClearFilter,
  onOpenCve,
  search,
  debounced,
  onSearchChange,
}) {
  const [cards, setCards] = useState([])
  const [errors, setErrors] = useState([])
  const [feedFailed, setFeedFailed] = useState(false)
  const [feedFailedRequestId, setFeedFailedRequestId] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadFeed = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setFeedFailed(false)
    setFeedFailedRequestId(null)
    loadCaseStudyFeed()
      .then(({ cards: loaded, errors: loadErrors }) => {
        if (cancelled) return
        setCards(loaded.filter(c => c.kind !== 'atlas'))
        setErrors(loadErrors)
      })
      .catch(err => {
        if (!cancelled) {
          setErrors([{ source: 'Feed', message: err.message || 'Failed to load' }])
          setFeedFailed(true)
          setFeedFailedRequestId(err?.requestId || null)
          notifyApiError(err)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => loadFeed(), [loadFeed])

  const filtered = useMemo(
    () => filterCaseStudyCards(cards, debounced),
    [cards, debounced],
  )

  const campaigns = useMemo(
    () => cards.filter(isCampaignArticle).slice(0, 5),
    [cards],
  )

  return (
    <div className="cs-panel">
      <div className="cs-search-row">
        <input
          type="search"
          className="cs-search-input"
          placeholder="Search tools, vendors, techniques..."
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          aria-label="Search headlines"
        />
        {search && (
          <button
            type="button"
            className="cs-search-clear mono"
            onClick={() => {
              onSearchChange('')
              onClearFilter?.()
            }}
            aria-label="Clear search"
          >
            ×
          </button>
        )}
      </div>

      {initialSearch && search === initialSearch && (
        <p className="cs-filter-banner mono" role="status">
          Filtered from investigation context: <strong>{initialSearch}</strong>
        </p>
      )}

      {errors.length > 0 && (
        <ul className="cs-source-errors" role="status">
          {errors.map(err => (
            <li key={err.source} className="cs-source-error mono">
              // {err.source}: {err.message}
              {feedFailed && feedFailedRequestId && (
                <>
                  {' '}
                  (<a href={ingestLogUrl({ level: 'ERROR', requestId: feedFailedRequestId })}>
                    ref: {feedFailedRequestId}
                  </a>)
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {feedFailed && (
        <button type="button" className="cs-retry-btn mono" onClick={loadFeed}>
          Retry
        </button>
      )}

      <div className="cs-layout">
        <section className="cs-main" aria-labelledby="cs-headlines-heading">
          <h2 id="cs-headlines-heading" className="cs-section-label mono">HEADLINES</h2>
          {loading ? (
            <SkeletonCards count={5} />
          ) : filtered.length === 0 ? (
            <p className="cs-empty mono">
              {debounced
                ? `No headlines found for "${debounced}"`
                : '// No headline items loaded — check source errors above'}
            </p>
          ) : (
            <div className="cs-feed">
              {filtered.map(card => (
                <FeedCard key={card.id} card={card} query={debounced} onOpenCve={onOpenCve} />
              ))}
            </div>
          )}
        </section>

        <aside className="cs-sidebar" aria-label="Campaign highlights">
          <section className="cs-sidebar-section" aria-labelledby="cs-campaign-heading">
            <h2 id="cs-campaign-heading" className="cs-section-label mono">ACTIVE CAMPAIGNS</h2>
            {loading ? (
              <SkeletonCards count={3} />
            ) : campaigns.length === 0 ? (
              <p className="cs-sidebar-empty mono">// No campaign headlines in current feeds</p>
            ) : (
              <div className="cs-feed cs-feed-grid">
                {campaigns.map(card => (
                  <FeedCard key={card.id} card={card} query={debounced} onOpenCve={onOpenCve} />
                ))}
              </div>
            )}
          </section>
        </aside>
      </div>
    </div>
  )
}
