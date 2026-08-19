import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  filterCaseStudyCards,
  loadCaseStudyFeed,
} from '../../utils/caseStudyFeed.js'
import { notifyApiError } from '../Toast.jsx'
import { FeedCard, SkeletonCards } from './shared.jsx'

export default function AtlasPanel({ onOpenCve, debounced = '' }) {
  const [cards, setCards] = useState([])
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setFailed(false)
    loadCaseStudyFeed()
      .then(({ cards: loaded }) => {
        if (cancelled) return
        setCards(loaded.filter(c => c.kind === 'atlas'))
      })
      .catch(err => {
        if (!cancelled) {
          setCards([])
          setFailed(true)
          notifyApiError(err)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => load(), [load])

  const filtered = useMemo(
    () => filterCaseStudyCards(cards, debounced),
    [cards, debounced],
  )

  return (
    <section className="cs-panel" aria-labelledby="cs-atlas-panel-heading">
      <h2 id="cs-atlas-panel-heading" className="cs-section-label mono">ATLAS CASE STUDIES</h2>
      {loading ? (
        <SkeletonCards count={5} />
      ) : failed ? (
        <p className="cs-empty mono">// Failed to load ATLAS case studies</p>
      ) : filtered.length === 0 ? (
        <p className="cs-empty mono">// No ATLAS case studies loaded</p>
      ) : (
        <div className="cs-feed">
          {filtered.map(card => (
            <FeedCard key={card.id} card={card} query={debounced} onOpenCve={onOpenCve} />
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
