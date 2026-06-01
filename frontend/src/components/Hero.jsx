import { useState, useEffect, useRef } from 'react'
import { fetchCVEs } from '../api.js'
import './Hero.css'

const STACK_KEY = 'briefr_stack'

export default function Hero({ activeStack, onStackChange }) {
  const [stack, setStack] = useState(() => {
    try { return localStorage.getItem(STACK_KEY) || '' } catch { return '' }
  })
  const [matchCount, setMatchCount] = useState(null)
  const [matchLoading, setMatchLoading] = useState(false)
  const debounceRef = useRef(null)
  const stackRef = useRef(stack)

  stackRef.current = stack

  useEffect(() => {
    try { localStorage.setItem(STACK_KEY, stack) } catch {}
  }, [stack])

  // Apply saved stack to feed on first load
  useEffect(() => {
    const trimmed = stack.trim()
    if (trimmed && !activeStack) {
      onStackChange(trimmed)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Sync when stack cleared from sidebar
  useEffect(() => {
    if (activeStack !== stackRef.current) {
      setStack(activeStack || '')
    }
  }, [activeStack])

  useEffect(() => {
    const trimmed = stack.trim()
    if (!trimmed) {
      setMatchCount(null)
      setMatchLoading(false)
      onStackChange('')
      return
    }

    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setMatchLoading(true)
      onStackChange(trimmed)
      fetchCVEs({ stack: trimmed, limit: 1, page: 1 })
        .then(data => setMatchCount(data.total ?? 0))
        .catch(() => setMatchCount(null))
        .finally(() => setMatchLoading(false))
    }, 600)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [stack, onStackChange])

  function handleClear() {
    setStack('')
    onStackChange('')
    setMatchCount(null)
  }

  return (
    <section className="hero" aria-label="BRIEFR brief">
      <h1 className="hero-heading">
        <em>What broke overnight.</em>
      </h1>
      <p className="hero-sub">
        Live CVE intelligence filtered for your stack. No noise, no filler.
      </p>

      <div className="hero-stack-bar" role="search" aria-label="Filter CVEs by tech stack">
        <label htmlFor="stack-input" className="stack-label">STACK //</label>
        <input
          id="stack-input"
          type="text"
          className="stack-input"
          value={stack}
          onChange={e => setStack(e.target.value)}
          placeholder="nginx, python, linux kernel, postgres..."
          aria-label="Enter your technology stack to filter CVEs"
          autoComplete="off"
          spellCheck="false"
        />
        {stack.trim() && (
          <button
            type="button"
            className="stack-clear-input-btn"
            onClick={handleClear}
            aria-label="Clear stack filter"
          >
            ×
          </button>
        )}
      </div>

      {stack.trim() && (matchLoading || matchCount != null) && (
        <p className="stack-match-count mono" aria-live="polite">
          {matchLoading
            ? 'Counting matches…'
            : `${matchCount.toLocaleString()} CVE${matchCount === 1 ? '' : 's'} match your stack`}
          {!matchLoading && activeStack && (
            <span className="stack-match-hint"> · feed filtered</span>
          )}
        </p>
      )}
    </section>
  )
}
