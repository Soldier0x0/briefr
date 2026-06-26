import { useState, useEffect, useRef } from 'react'
import { STACK_STORAGE_KEY } from '../utils/cveFilters.js'

const DEBOUNCE_MS = 400

export default function StackContextBar({ stack, onStackChange }) {
  const [local, setLocal] = useState(stack || '')
  const debounceRef = useRef(null)

  useEffect(() => {
    setLocal(stack || '')
  }, [stack])

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
  }, [])

  function commit(val) {
    const trimmed = val.trim()
    try {
      if (trimmed) localStorage.setItem(STACK_STORAGE_KEY, trimmed)
      else localStorage.removeItem(STACK_STORAGE_KEY)
    } catch { /* ignore */ }
    window.dispatchEvent(new CustomEvent('briefr-stack-change'))
    onStackChange(trimmed)
  }

  function handleChange(e) {
    const val = e.target.value
    setLocal(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => commit(val), DEBOUNCE_MS)
  }

  function removeTerm(term) {
    const parts = local.split(',').map(s => s.trim()).filter(Boolean)
    const next = parts.filter(p => p.toLowerCase() !== term.toLowerCase()).join(', ')
    setLocal(next)
    commit(next)
  }

  const terms = local.split(',').map(s => s.trim()).filter(Boolean)

  return (
    <div className="stack-context-bar" role="region" aria-label="Stack filter">
      <span className="stack-context-label">Stack</span>
      <input
        type="text"
        className="stack-context-input"
        value={local}
        onChange={handleChange}
        placeholder="nginx, python, postgres…"
        aria-label="Filter by your technology stack"
        autoComplete="off"
        spellCheck="false"
      />
      {terms.length > 0 && (
        <div className="stack-context-chips" aria-label="Active stack terms">
          {terms.map(term => (
            <button
              key={term}
              type="button"
              className="chip chip-active chip-removable"
              onClick={() => removeTerm(term)}
              aria-label={`Remove stack term ${term}`}
            >
              {term}
              <span aria-hidden="true">×</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
