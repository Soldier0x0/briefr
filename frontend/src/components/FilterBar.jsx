import { useState, useRef, useEffect } from 'react'
import { fetchCVEs } from '../api.js'
import { cvesToCsvRows, downloadCsv, exportFilename } from '../utils/exportCsv.js'
import './FilterBar.css'

const QUICK_FILTERS = [
  { id: 'all',      label: 'ALL' },
  { id: 'kev',      label: 'KEV' },
  { id: 'critical', label: 'CRITICAL' },
  { id: 'high',     label: 'HIGH' },
  { id: 'medium',   label: 'MEDIUM' },
  { id: 'poc',      label: 'PoC' },
]

export const VENDORS = [
  'Microsoft', 'Apache', 'Cisco', 'Google', 'Adobe', 'Linux',
  'Fortinet', 'Ivanti', 'VMware', 'Palo Alto', 'Oracle', 'Apple',
]

function deriveActive(filters) {
  if (filters.kev_only && !filters.poc_only && !filters.severity) return 'kev'
  if (filters.severity === 'CRITICAL' && !filters.kev_only && !filters.poc_only) return 'critical'
  if (filters.severity === 'HIGH'     && !filters.kev_only && !filters.poc_only) return 'high'
  if (filters.severity === 'MEDIUM'   && !filters.kev_only && !filters.poc_only) return 'medium'
  if (filters.poc_only && !filters.kev_only && !filters.severity) return 'poc'
  return 'all'
}

function parseVendors(vendorsStr) {
  if (!vendorsStr || !vendorsStr.trim()) return []
  return vendorsStr.split(',').map(v => v.trim()).filter(Boolean)
}

export default function FilterBar({
  filters,
  onFiltersChange,
  total,
  onGenerateDigest,
  searchFocusTrigger,
}) {
  const [localSearch, setLocalSearch] = useState(filters.search || '')
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState(null)
  const debounceRef  = useRef(null)
  const searchRef    = useRef(null)

  useEffect(() => {
    setLocalSearch(filters.search || '')
  }, [filters.search])

  useEffect(() => {
    if (searchFocusTrigger > 0 && searchRef.current) {
      searchRef.current.focus()
      searchRef.current.select()
    }
  }, [searchFocusTrigger])

  const active = deriveActive(filters)
  const selectedVendors = parseVendors(filters.vendors)

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

  function handleVendorClick(vendor) {
    const next = selectedVendors.includes(vendor)
      ? selectedVendors.filter(v => v !== vendor)
      : [...selectedVendors, vendor]
    onFiltersChange({ vendors: next.join(',') })
  }

  function clearVendors() {
    onFiltersChange({ vendors: '' })
  }

  async function handleExportCsv() {
    if (exporting) return
    setExporting(true)
    setExportError(null)
    try {
      const all = []
      let page = 1
      let pages = 1
      const limit = 50

      while (page <= pages && all.length < 500) {
        const data = await fetchCVEs({
          ...filters,
          page,
          limit,
        })
        pages = data.pages
        all.push(...data.data)
        if (!data.data.length) break
        page += 1
      }

      if (!all.length) {
        setExportError('No CVEs to export for current filters.')
        return
      }

      const rows = all.slice(0, 500)
      const csv = cvesToCsvRows(rows)
      downloadCsv(csv, exportFilename())
    } catch (err) {
      setExportError(err.message || 'Export failed. Is the API running?')
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
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
          <div className="filter-action-btns">
            <button
              className="digest-btn"
              onClick={onGenerateDigest}
              aria-label="Generate digest of current CVE results"
              title="Generate digest of currently visible CVEs"
            >
              GENERATE DIGEST
            </button>
            <button
              className="export-btn"
              onClick={handleExportCsv}
              disabled={exporting}
              aria-label="Export filtered CVEs to CSV"
              title="Export all filtered CVEs (up to 500) as CSV"
            >
              {exporting ? 'EXPORTING...' : 'EXPORT CSV'}
            </button>
          </div>

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

      {exportError && (
        <p className="export-error mono" role="alert">
          {exportError}
        </p>
      )}

      {active === 'all' && (
        <div className="vendor-filter-block">
          <div className="vendor-filter-header">
            <span className="vendor-filter-label mono">// VENDORS</span>
            {selectedVendors.length > 0 && (
              <button
                type="button"
                className="vendor-clear-btn mono"
                onClick={clearVendors}
                aria-label="Clear all vendor filters"
              >
                CLEAR ({selectedVendors.length})
              </button>
            )}
          </div>
          <div
            className="vendor-filter-row"
            role="group"
            aria-label="Filter by vendor (multi-select)"
          >
            {VENDORS.map(v => (
              <button
                key={v}
                type="button"
                className={`vendor-btn${selectedVendors.includes(v) ? ' active' : ''}`}
                onClick={() => handleVendorClick(v)}
                aria-pressed={selectedVendors.includes(v)}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
