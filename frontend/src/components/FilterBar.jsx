import { useState, useRef, useEffect } from 'react'
import './FilterBar.css'

const QUICK_FILTERS = [
  { id: 'all',      label: 'ALL' },
  { id: 'kev',      label: 'KEV' },
  { id: 'critical', label: 'CRITICAL' },
  { id: 'poc',      label: 'PoC' },
]

function deriveActive(filters) {
  if (filters.kev_only && !filters.poc_only && !filters.severity) return 'kev'
  if (filters.severity === 'CRITICAL' && !filters.kev_only && !filters.poc_only) return 'critical'
  if (filters.poc_only && !filters.kev_only && !filters.severity) return 'poc'
  return 'all'
}

export default function FilterBar({ filters, onFiltersChange, total }) {
  const [localSearch, setLocalSearch] = useState(filters.search || '')
  const debounceRef = useRef(null)

  useEffect(() => {
    setLocalSearch(filters.search || '')
  }, [filters.search])

  const active = deriveActive(filters)

  function handleQuickFilter(id) {
    const base = { severity: null, kev_only: false, poc_only: false }
    if (id === 'kev')      onFiltersChange({ ...base, kev_only: true })
    else if (id === 'critical') onFiltersChange({ ...base, severity: 'CRITICAL' })
    else if (id === 'poc') onFiltersChange({ ...base, poc_only: true })
    else                   onFiltersChange(base)
  }

  function handleSearchChange(e) {
    const val = e.target.value
    setLocalSearch(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      onFiltersChange({ search: val })
    }, 320)
  }

  return (
    <div className="filter-bar" role="toolbar" aria-label="CVE feed filters">
      <div className="filter-bar-left">
        <span className="filter-title">
          CVE FEED
          {total != null && (
            <span className="filter-count" aria-label={`${total} results`}>
              &nbsp;// {total.toLocaleString()}
            </span>
          )}
        </span>
      </div>

      <div className="filter-bar-right">
        <div className="filter-buttons" role="group" aria-label="Quick filters">
          {QUICK_FILTERS.map(f => (
            <button
              key={f.id}
              className={`filter-btn${active === f.id ? ' active' : ''}`}
              onClick={() => handleQuickFilter(f.id)}
              aria-label={`Filter: ${f.label}`}
              aria-pressed={active === f.id}
            >
              {f.label}
            </button>
          ))}
        </div>

        <input
          type="search"
          className="filter-search"
          value={localSearch}
          onChange={handleSearchChange}
          placeholder="search CVE-ID or keyword..."
          aria-label="Search CVEs by ID or keyword"
          autoComplete="off"
          spellCheck="false"
        />
      </div>
    </div>
  )
}
