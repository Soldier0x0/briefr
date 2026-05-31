import { useState, useRef, useEffect } from 'react'
import './FilterBar.css'

const QUICK_FILTERS = [
  { id: 'all',      label: 'ALL' },
  { id: 'kev',      label: 'KEV' },
  { id: 'critical', label: 'CRITICAL' },
  { id: 'high',     label: 'HIGH' },
  { id: 'medium',   label: 'MEDIUM' },
  { id: 'poc',      label: 'PoC' },
]

function deriveActive(filters) {
  if (filters.kev_only && !filters.poc_only && !filters.severity) return 'kev'
  if (filters.severity === 'CRITICAL' && !filters.kev_only && !filters.poc_only) return 'critical'
  if (filters.severity === 'HIGH'     && !filters.kev_only && !filters.poc_only) return 'high'
  if (filters.severity === 'MEDIUM'   && !filters.kev_only && !filters.poc_only) return 'medium'
  if (filters.poc_only && !filters.kev_only && !filters.severity) return 'poc'
  return 'all'
}

export default function FilterBar({
  filters,
  onFiltersChange,
  total,
  onGenerateDigest,
  searchFocusTrigger,
}) {
  const [localSearch, setLocalSearch] = useState(filters.search || '')
  const debounceRef  = useRef(null)
  const searchRef    = useRef(null)

  // Sync local search when filters.search cleared from outside
  useEffect(() => {
    setLocalSearch(filters.search || '')
  }, [filters.search])

  // / shortcut: focus search input when trigger increments
  useEffect(() => {
    if (searchFocusTrigger > 0 && searchRef.current) {
      searchRef.current.focus()
      searchRef.current.select()
    }
  }, [searchFocusTrigger])

  const active = deriveActive(filters)

  function handleQuickFilter(id) {
    const base = { severity: null, kev_only: false, poc_only: false }
    if (id === 'kev')           onFiltersChange({ ...base, kev_only: true })
    else if (id === 'critical') onFiltersChange({ ...base, severity: 'CRITICAL' })
    else if (id === 'high')     onFiltersChange({ ...base, severity: 'HIGH' })
    else if (id === 'medium')   onFiltersChange({ ...base, severity: 'MEDIUM' })
    else if (id === 'poc')      onFiltersChange({ ...base, poc_only: true })
    else                        onFiltersChange(base)
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
        <span className="filter-title mono">
          CVE FEED
          {total != null && (
            <span className="filter-count" aria-label={`${total} results`}>
              &nbsp;// {total.toLocaleString()}
            </span>
          )}
        </span>
      </div>

      <div className="filter-bar-right">
        <button
          className="digest-btn"
          onClick={onGenerateDigest}
          aria-label="Generate digest of current CVE results"
          title="Generate digest of currently visible CVEs"
        >
          GENERATE DIGEST
        </button>

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
          ref={searchRef}
          type="search"
          className="filter-search"
          value={localSearch}
          onChange={handleSearchChange}
          placeholder="search CVE-ID or keyword..."
          aria-label="Search CVEs by ID or keyword (press / to focus)"
          autoComplete="off"
          spellCheck="false"
        />
      </div>
    </div>
  )
}
