import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Leaf component: tracks visible CVE card indices on scroll without re-rendering
 * the feed list (Track I4).
 */
export default function FeedVisibleRange({ listRootRef, cardCount, className = 'filter-showing' }) {
  const [range, setRange] = useState(null)
  const rafRef = useRef(null)

  const compute = useCallback(() => {
    const root = listRootRef?.current
    if (!root) {
      setRange(null)
      return
    }

    const cards = root.querySelectorAll('.cve-card')
    if (!cards.length) {
      setRange(null)
      return
    }

    const viewportH = window.innerHeight
    let first = null
    let last = null

    for (let idx = 0; idx < cards.length; idx += 1) {
      const rect = cards[idx].getBoundingClientRect()
      if (rect.bottom > 0 && rect.top < viewportH) {
        if (first === null) first = idx
        last = idx
      }
    }

    if (first === null) {
      first = 0
      last = 0
    }

    setRange({ start: first + 1, end: last + 1 })
  }, [listRootRef])

  const schedule = useCallback(() => {
    if (rafRef.current != null) return
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null
      compute()
    })
  }, [compute])

  useEffect(() => {
    schedule()
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule, { passive: true })
    return () => {
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }
  }, [schedule, cardCount])

  if (!range || range.end <= 0) return null

  return (
    <>
      <span className="filter-meta-sep" aria-hidden="true">
        {' '}
        ·
        {' '}
      </span>
      <span
        className={className}
        aria-label={`Showing ${range.start} through ${range.end}`}
      >
        Showing {range.start}-{range.end}
      </span>
    </>
  )
}
