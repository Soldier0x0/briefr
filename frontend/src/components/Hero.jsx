import { useState, useEffect, useRef } from 'react'
import { fetchCVEs } from '../api.js'
import { STACK_STORAGE_KEY, toApiCveParams } from '../utils/cveFilters.js'
import './Hero.css'
const DEBOUNCE_MS = 800

export default function Hero({ activeStack, onBrief, onClearStack }) {
  const [stack, setStack] = useState(() => {
    try { return localStorage.getItem(STACK_STORAGE_KEY) || '' } catch { return '' }
  })
  const [matchCount, setMatchCount] = useState(null)
  const [searching, setSearching] = useState(false)
  const debounceRef = useRef(null)
  const previewSeqRef = useRef(0)
  const hadAppliedStackRef = useRef(false)

  useEffect(() => {
    try { localStorage.setItem(STACK_STORAGE_KEY, stack) } catch {}
    window.dispatchEvent(new CustomEvent('briefr-stack-change'))
  }, [stack])

  // Clear input when stack filter removed from feed (× clear stack)
  useEffect(() => {
    if (activeStack) {
      hadAppliedStackRef.current = true
      return
    }
    if (hadAppliedStackRef.current) {
      setStack('')
      setMatchCount(null)
      setSearching(false)
      hadAppliedStackRef.current = false
    }
  }, [activeStack])

  // Preview count only — does not filter the feed until BRIEF
  useEffect(() => {
    const trimmed = stack.trim()
    if (!trimmed) {
      setMatchCount(null)
      setSearching(false)
      return
    }

    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      const seq = ++previewSeqRef.current
      setSearching(true)
      fetchCVEs(toApiCveParams({ stack: trimmed, limit: 1, page: 1 }))
        .then(data => {
          if (seq !== previewSeqRef.current) return
          setMatchCount(data.total ?? 0)
        })
        .catch(() => {
          if (seq !== previewSeqRef.current) return
          setMatchCount(null)
        })
        .finally(() => {
          if (seq !== previewSeqRef.current) return
          setSearching(false)
        })
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [stack])

  function applyBrief() {
    const trimmed = stack.trim()
    if (trimmed) onBrief(trimmed)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault()
      applyBrief()
    }
  }

  const showCountLine = stack.trim().length > 0

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
          onKeyDown={handleKeyDown}
          placeholder="nginx, python, linux kernel, postgres..."
          aria-label="Enter your technology stack to filter CVEs"
          autoComplete="off"
          spellCheck="false"
        />
        <button
          type="button"
          className="stack-brief-btn"
          onClick={applyBrief}
          disabled={!stack.trim()}
          aria-label="Filter CVE feed by entered stack"
        >
          BRIEF
        </button>
      </div>

      {showCountLine && (
        <p className="stack-match-count mono" aria-live="polite">
          {searching
            ? 'Searching...'
            : matchCount === null
              ? 'Searching...'
              : `${matchCount.toLocaleString()} CVE${matchCount === 1 ? '' : 's'} match your stack`}
        </p>
      )}
    </section>
  )
}
