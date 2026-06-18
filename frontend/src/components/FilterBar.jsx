import { useState, useRef, useEffect } from 'react'
import { fetchCVEsForExport } from '../api.js'
import { STACK_STORAGE_KEY, toApiCveParams } from '../utils/cveFilters.js'
import { cvesToCsvRows, downloadCsv, exportFilename } from '../utils/exportCsv.js'
import './FilterBar.css'

const STACK_DEBOUNCE_MS = 400

const QUICK_FILTERS = [
  { id: 'all',      label: 'ALL' },
  { id: 'watchlist', label: 'WATCHLIST' },
  { id: 'kev',      label: 'KEV' },
  { id: 'critical', label: 'CRITICAL' },
  { id: 'high',     label: 'HIGH' },
  { id: 'medium',   label: 'MEDIUM' },
  { id: 'poc',      label: 'PoC' },
]

export const VENDORS = [
  'Microsoft', 'Apache', 'Cisco', 'Google', 'Adobe', 'Linux', 'Apple', 'Oracle',
  'Fortinet', 'Ivanti', 'VMware', 'Palo Alto', 'Amazon', 'IBM', 'Dell', 'HP',
  'Juniper', 'Citrix', 'F5', 'Check Point', 'SAP', 'Siemens', 'MongoDB', 'Atlassian',
  'GitLab', 'Jenkins', 'Docker', 'Kubernetes', 'WordPress', 'PHP', 'Python', 'Node.js',
]

function deriveActive(filters) {
  if (filters.watchlist_only && !filters.kev_only && !filters.poc_only && !filters.severity) {
    return 'watchlist'
  }
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

export function hasActiveFilters(filters) {
  return !!(
    (filters.search && filters.search.trim()) ||
    filters.stack ||
    filters.technique ||
    filters.vendors ||
    filters.kev_only ||
    filters.poc_only ||
    filters.epss_min != null ||
    filters.severity ||
    filters.published_on ||
    filters.my_stack_only ||
    filters.ai_profile_match ||
    filters.watchlist_only
  )
}

export default function FilterBar({
  filters,
  onFiltersChange,
  total,
  showingRange,
  onGenerateDigest,
  searchFocusTrigger,
}) {
  const [localSearch, setLocalSearch] = useState(filters.search || '')
  const [localStack, setLocalStack] = useState(() => filters.stack || '')
  const [exporting, setExporting] = useState(null)
  const [exportError, setExportError] = useState(null)
  const [exportSuccess, setExportSuccess] = useState(null)
  const debounceRef  = useRef(null)
  const stackDebounceRef = useRef(null)
  const exportSuccessTimeoutRef = useRef(null)
  const searchRef    = useRef(null)

  useEffect(() => {
    setLocalSearch(filters.search || '')
  }, [filters.search])

  useEffect(() => {
    setLocalStack(filters.stack || '')
  }, [filters.stack])

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      if (stackDebounceRef.current) clearTimeout(stackDebounceRef.current)
      if (exportSuccessTimeoutRef.current) clearTimeout(exportSuccessTimeoutRef.current)
    }
  }, [])

  useEffect(() => {
    if (searchFocusTrigger > 0 && searchRef.current) {
      searchRef.current.focus()
      searchRef.current.select()
    }
  }, [searchFocusTrigger])

  const active = deriveActive(filters)
  const selectedVendors = parseVendors(filters.vendors)

  function handleQuickFilter(id) {
    const base = { severity: null, kev_only: false, poc_only: false, watchlist_only: false }
    if (id === 'watchlist')     onFiltersChange({ ...base, watchlist_only: true })
    else if (id === 'kev')           onFiltersChange({ ...base, kev_only: true })
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

  function handleStackChange(e) {
    const val = e.target.value
    setLocalStack(val)
    if (stackDebounceRef.current) clearTimeout(stackDebounceRef.current)
    stackDebounceRef.current = setTimeout(() => {
      const trimmed = val.trim()
      try {
        localStorage.setItem(STACK_STORAGE_KEY, trimmed)
      } catch { /* ignore */ }
      window.dispatchEvent(new CustomEvent('briefr-stack-change'))
      onFiltersChange({ stack: trimmed })
    }, STACK_DEBOUNCE_MS)
  }

  function handleStackClear() {
    setLocalStack('')
    if (stackDebounceRef.current) clearTimeout(stackDebounceRef.current)
    try {
      localStorage.removeItem(STACK_STORAGE_KEY)
    } catch { /* ignore */ }
    window.dispatchEvent(new CustomEvent('briefr-stack-change'))
    onFiltersChange({ stack: '' })
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

  async function fetchExportRows() {
    const data = await fetchCVEsForExport(toApiCveParams(filters))
    const rows = data.data || []
    if (!rows.length) {
      throw new Error('No CVEs to export for current filters.')
    }
    return rows
  }

  function showExportSuccess(message) {
    if (exportSuccessTimeoutRef.current) clearTimeout(exportSuccessTimeoutRef.current)
    setExportSuccess(message)
    exportSuccessTimeoutRef.current = window.setTimeout(() => {
      setExportSuccess(null)
      exportSuccessTimeoutRef.current = null
    }, 4000)
  }

  async function handleExportCsv() {
    if (exporting) return
    setExporting('csv')
    setExportError(null)
    setExportSuccess(null)
    try {
      const rows = await fetchExportRows()
      const csv = cvesToCsvRows(rows)
      downloadCsv(csv, exportFilename())
      showExportSuccess(`Downloaded ${rows.length.toLocaleString()} CVEs as CSV.`)
    } catch (err) {
      setExportError(err.message || 'Export failed. Restart the backend and try again.')
    } finally {
      setExporting(null)
    }
  }

  async function handleExportXlsx() {
    if (exporting) return
    setExporting('xlsx')
    setExportError(null)
    setExportSuccess(null)
    try {
      const rows = await fetchExportRows()
      const { downloadCvesXlsx, exportXlsxFilename } = await import('../utils/exportXlsx.js')
      await downloadCvesXlsx(rows, exportXlsxFilename())
      showExportSuccess(`Downloaded ${rows.length.toLocaleString()} CVEs as Excel (.xlsx).`)
    } catch (err) {
      setExportError(err.message || 'Excel export failed. Restart the backend and try again.')
    } finally {
      setExporting(null)
    }
  }

  return (
    <div className="filter-toolbar">
      <div className="filter-bar" role="toolbar" aria-label="CVE feed filters">
        <div className="filter-bar-top">
          <div className="filter-bar-left">
            <span className="filter-title mono">
              CVE FEED
              {total != null && (
                <>
                  <span className="filter-count" aria-label={`${total} results`}>
                    &nbsp;//{' '}
                    {hasActiveFilters(filters)
                      ? `${total.toLocaleString()} matches`
                      : total.toLocaleString()}
                  </span>
                  {showingRange && showingRange.end > 0 && (
                    <>
                      <span className="filter-meta-sep" aria-hidden="true">
                        {' '}
                        ·
                        {' '}
                      </span>
                      <span
                        className="filter-showing"
                        aria-label={`Showing ${showingRange.start} through ${showingRange.end}`}
                      >
                        Showing {showingRange.start}-{showingRange.end}
                      </span>
                    </>
                  )}
                </>
              )}
              {filters.stack && (
                <button
                  type="button"
                  className="filter-stack-clear mono"
                  onClick={() => onFiltersChange({ stack: '' })}
                  aria-label="Clear stack filter and show all CVEs"
                >
                  × clear stack
                </button>
              )}
              {filters.technique && (
                <button
                  type="button"
                  className="filter-stack-clear mono"
                  onClick={() => onFiltersChange({ technique: '' })}
                  aria-label="Clear ATT&CK technique filter"
                >
                  × clear technique
                </button>
              )}
              {filters.published_on && (
                <button
                  type="button"
                  className="filter-stack-clear mono"
                  onClick={() => onFiltersChange({ published_on: '' })}
                  aria-label="Clear published date filter"
                >
                  × clear {filters.published_on}
                </button>
              )}
            </span>
          </div>

          <div className="filter-action-btns">
            <button
              type="button"
              className="digest-btn"
              onClick={onGenerateDigest}
              aria-label="Generate digest of current CVE results"
              title="Generate digest of currently visible CVEs"
            >
              GENERATE DIGEST
            </button>
            <button
              type="button"
              className="export-btn"
              onClick={handleExportCsv}
              disabled={!!exporting}
              aria-label="Export filtered CVEs to CSV"
              title="Export all filtered CVEs (up to 500) as CSV for integrations"
            >
              {exporting === 'csv' ? 'EXPORTING...' : 'EXPORT CSV'}
            </button>
            <button
              type="button"
              className="export-btn export-btn-xlsx"
              onClick={handleExportXlsx}
              disabled={!!exporting}
              aria-label="Export filtered CVEs to Excel"
              title="Export filtered CVEs (up to 500) as a formatted Excel workbook"
            >
              {exporting === 'xlsx' ? 'EXPORTING...' : 'EXPORT XLSX'}
            </button>
          </div>
        </div>

        <div className="filter-bar-bottom">
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

      <div className="filter-stack-row" role="search" aria-label="Filter CVEs by technology stack">
        <label htmlFor="feed-stack-input" className="filter-stack-label mono">
          STACK //
        </label>
        <input
          id="feed-stack-input"
          type="text"
          className="filter-stack-input"
          value={localStack}
          onChange={handleStackChange}
          placeholder="nginx, python, linux kernel..."
          aria-label="Enter stack terms to filter the CVE feed"
          autoComplete="off"
          spellCheck="false"
        />
        {localStack && (
          <button
            type="button"
            className="filter-stack-clear-btn mono"
            onClick={handleStackClear}
            aria-label="Clear stack filter"
          >
            ×
          </button>
        )}
      </div>

      {exportError && (
        <p className="export-error mono" role="alert">
          {exportError}
        </p>
      )}
      {exportSuccess && (
        <p className="export-success mono" role="status">
          {exportSuccess}
        </p>
      )}

      {active === 'all' && (
        <div className="vendor-filter-block">
          <div className="vendor-filter-header">
            <span className="vendor-filter-label mono">// COMMON VENDORS</span>
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
    </div>
  )
}
