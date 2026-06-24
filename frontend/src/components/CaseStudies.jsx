import { useEffect, useMemo, useState } from 'react'
import {
  filterCaseStudyCards,
  highlightParts,
  isCampaignArticle,
  loadCaseStudyFeed,
  relativeDate,
} from '../utils/caseStudyFeed.js'
import './CaseStudies.css'

function SkeletonCards({ count = 4 }) {
  return (
    <ul className="cs-skeleton-list" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <li key={i} className="cs-skeleton-card" />
      ))}
    </ul>
  )
}

function TechniqueChips({ techniques }) {
  if (!techniques?.length) return null
  return (
    <div className="cs-tech-chips" aria-label="Techniques referenced">
      {techniques.slice(0, 6).map(tid => (
        <span key={tid} className="cs-tech-chip mono">{tid}</span>
      ))}
    </div>
  )
}

function FeedCard({ card, query }) {
  const titleParts = highlightParts(card.title, query)
  const descParts = highlightParts(card.description, query)

  return (
    <article className="cs-card">
      <div className="cs-card-top">
        <span className={`cs-source-badge mono${card.kind === 'atlas' ? ' cs-source-badge-atlas' : ''}`}>
          {card.source}
        </span>
        <time className="cs-card-date mono" dateTime={card.publishedAt}>
          {relativeDate(card.publishedAt)}
        </time>
      </div>
      <h3 className="cs-card-title">
        <a href={card.url} target="_blank" rel="noopener noreferrer">
          {titleParts.map((p, i) =>
            p.match ? <mark key={i} className="cs-highlight">{p.text}</mark> : <span key={i}>{p.text}</span>,
          )}
        </a>
      </h3>
      {card.actor && (
        <p className="cs-card-actor mono">Actor: {card.actor}</p>
      )}
      {card.target && card.kind === 'atlas' && (
        <p className="cs-card-target mono">Target: {card.target}</p>
      )}
      <p className="cs-card-desc">
        {descParts.map((p, i) =>
          p.match ? <mark key={i} className="cs-highlight">{p.text}</mark> : <span key={i}>{p.text}</span>,
        )}
      </p>
      <TechniqueChips techniques={card.techniques} />
    </article>
  )
}

export default function CaseStudies({ initialSearch = '', onClearFilter }) {
  const [cards, setCards] = useState([])
  const [errors, setErrors] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState(initialSearch)
  const [debounced, setDebounced] = useState(initialSearch)


  useEffect(() => {
    setSearch(initialSearch)
    setDebounced(initialSearch)
  }, [initialSearch])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    loadCaseStudyFeed()
      .then(({ cards: loaded, errors: loadErrors }) => {
        if (cancelled) return
        setCards(loaded)
        setErrors(loadErrors)
      })
      .catch(err => {
        if (!cancelled) {
          setErrors([{ source: 'Feed', message: err.message || 'Failed to load' }])
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    const id = setTimeout(() => setDebounced(search), 400)
    return () => clearTimeout(id)
  }, [search])

  const filtered = useMemo(
    () => filterCaseStudyCards(cards, debounced),
    [cards, debounced],
  )

  const atlasLatest = useMemo(
    () => cards.filter(c => c.kind === 'atlas').slice(0, 3),
    [cards],
  )

  const campaigns = useMemo(
    () => cards.filter(isCampaignArticle).slice(0, 5),
    [cards],
  )

  return (
    <div className="case-studies" role="region" aria-label="Case studies and attack narratives">
      <header className="cs-hero">
        <p className="cs-hero-kicker mono">REAL-WORLD ATTACK CONTEXT</p>
        <h1 className="cs-hero-title">Case Studies</h1>
        <p className="cs-hero-sub">
          Real-world attack stories from security news and MITRE ATLAS research — how incidents
          unfolded in the wild. CVE severity, KEV deadlines, and patching stay on BRIEF and FEED.
        </p>
      </header>

      <div className="cs-search-row">
        <input
          type="search"
          className="cs-search-input"
          placeholder="Search tools, vendors, techniques..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          aria-label="Search incidents and news"
        />
        {search && (
          <button
            type="button"
            className="cs-search-clear mono"
            onClick={() => {
              setSearch('')
              setDebounced('')
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
            </li>
          ))}
        </ul>
      )}

      <div className="cs-layout">
        <section className="cs-main" aria-labelledby="cs-feed-heading">
          <h2 id="cs-feed-heading" className="cs-section-label mono">INCIDENTS &amp; NEWS</h2>
          {loading ? (
            <SkeletonCards count={5} />
          ) : filtered.length === 0 ? (
            <p className="cs-empty mono">
              {debounced
                ? `No incidents or news found for "${debounced}"`
                : '// No feed items loaded — check source errors above'}
            </p>
          ) : (
            <div className="cs-feed">
              {filtered.map(card => (
                <FeedCard key={card.id} card={card} query={debounced} />
              ))}
            </div>
          )}
        </section>

        <aside className="cs-sidebar" aria-label="Sidebar highlights">
          <section className="cs-sidebar-section" aria-labelledby="cs-atlas-heading">
            <h2 id="cs-atlas-heading" className="cs-section-label mono">LATEST FROM ATLAS</h2>
            {loading ? (
              <SkeletonCards count={3} />
            ) : atlasLatest.length === 0 ? (
              <p className="cs-sidebar-empty mono">// No ATLAS case studies loaded</p>
            ) : (
              <div className="cs-feed">
                {atlasLatest.map(card => (
                  <FeedCard key={card.id} card={card} query={debounced} />
                ))}
              </div>
            )}
          </section>

          <section className="cs-sidebar-section" aria-labelledby="cs-campaign-heading">
            <h2 id="cs-campaign-heading" className="cs-section-label mono">ACTIVE CAMPAIGNS</h2>
            {loading ? (
              <SkeletonCards count={3} />
            ) : campaigns.length === 0 ? (
              <p className="cs-sidebar-empty mono">// No campaign headlines in current feeds</p>
            ) : (
              <div className="cs-feed cs-feed-grid">
                {campaigns.map(card => (
                  <FeedCard key={card.id} card={card} query={debounced} />
                ))}
              </div>
            )}
          </section>
        </aside>
      </div>
    </div>
  )
}
