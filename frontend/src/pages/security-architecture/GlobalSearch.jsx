import { useEffect, useRef, useState } from 'react'
import { fetchSecurityArchitectureSearch } from '../../api.js'
import { isAnalystHiddenSection, resolveAnalystSection } from './constants.js'

const TYPE_LABEL = {
  components: 'ROUTER', endpoints: 'ENDPOINT', jobs: 'JOB', tables: 'TABLE',
  trust_boundaries: 'TRUST BOUNDARY', controls: 'CONTROL', abuse_cases: 'ABUSE CASE',
  threat_scenarios: 'SCENARIO', security_decisions: 'DECISION', risks: 'RISK',
  reviews: 'REVIEW', mitre_technique: 'MITRE',
}

/**
 * Global search (spec §5.17, §8 TM-5): in-module search bar over the corpus
 * + live MITRE technique names + control titles + API paths (backend
 * merge.search_corpus / search_mitre_techniques). Arrow-key navigable,
 * Enter opens the section a result belongs to (§5.17: "Results grouped by
 * entity type; arrow-key navigable; Enter opens section + selection").
 */
export default function GlobalSearch({ onOpenSection }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const debounceRef = useRef(null)
  const rootRef = useRef(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const q = query.trim()
    if (!q) {
      setResults([])
      setOpen(false)
      return undefined
    }
    let active = true
    debounceRef.current = setTimeout(() => {
      fetchSecurityArchitectureSearch(q)
        .then(res => {
          if (!active) return
          const visible = (res.results || []).filter(
            (r) => !isAnalystHiddenSection(r.section),
          )
          setResults(visible)
          setOpen(Boolean(visible.length))
          setActiveIndex(-1)
        })
        .catch(() => { /* search bar just shows no results */ })
    }, 180)
    return () => {
      active = false
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query])

  useEffect(() => {
    function onOutside(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [])

  function select(result) {
    setOpen(false)
    setQuery('')
    // Sections don't yet take an arbitrary id-scoped filter (only status/
    // severity/origin/type per the generic section reads) -- search opens
    // the right section; landing on the exact row is a future enhancement,
    // not invented here.
    onOpenSection(resolveAnalystSection(result.section))
  }

  function onKeyDown(e) {
    if (!open || results.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex(i => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault()
      select(results[activeIndex])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const grouped = results.reduce((acc, r) => {
    (acc[r.type] ||= []).push(r)
    return acc
  }, {})

  return (
    <div className="sa-search" ref={rootRef}>
      <label className="sr-only" htmlFor="sa-global-search">Search security architecture</label>
      <input
        id="sa-global-search"
        type="text"
        className="sa-search-input mono"
        placeholder="Search controls, risks, techniques…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => { if (results.length) setOpen(true) }}
        onKeyDown={onKeyDown}
        role="combobox"
        aria-expanded={open}
        aria-controls="sa-search-results"
        aria-autocomplete="list"
      />
      {open && (
        <div className="sa-search-results" id="sa-search-results" role="listbox">
          {results.length === 0 ? (
            <p className="sa-search-empty mono">No matches.</p>
          ) : (
            Object.entries(grouped).map(([type, items]) => (
              <div key={type} className="sa-search-group">
                <p className="sa-subsection-label mono">{TYPE_LABEL[type] || type}</p>
                {items.map((r) => {
                  const globalIndex = results.indexOf(r)
                  return (
                    <button
                      key={`${r.type}-${r.id}`}
                      type="button"
                      role="option"
                      aria-selected={globalIndex === activeIndex}
                      className={`sa-search-result${globalIndex === activeIndex ? ' active' : ''}`}
                      onMouseEnter={() => setActiveIndex(globalIndex)}
                      onClick={() => select(r)}
                    >
                      <span className="sa-search-result-title">{r.title}</span>
                      {r.summary && <span className="sa-search-result-summary">{r.summary}</span>}
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
