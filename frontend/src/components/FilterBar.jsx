import { useState, useRef, useEffect } from 'react'
import {
  agreeStackBackfill,
  fetchCVEsForExport,
  fetchStackBackfillRun,
  fetchStackCoverage,
  resumeStackBackfill,
} from '../api.js'
import { notifyExportError, notifyExportProgress, notifyExportSuccess } from './Toast.jsx'
import { notifyApiError } from './Toast.jsx'
import { toApiCveParams } from '../utils/cveFilters.js'
import { saveUserStack } from '../utils/userStack.js'
import { cvesToCsvRows, downloadCsv, exportFilename } from '../utils/exportCsv.js'
import ControlTooltip from './ControlTooltip.jsx'
import FeedVisibleRange from './FeedVisibleRange.jsx'
import { nextLocalStack } from '../utils/stackLocalSync.js'
import './FilterBar.css'

const STACK_DEBOUNCE_MS = 400

const QUICK_FILTERS = [
  { id: 'all',         label: 'ALL',         explain: 'All severities — no quick filter applied.' },
  { id: 'watchlist',   label: 'WATCHLIST',   explain: 'CVEs you have pinned to your watchlist.' },
  { id: 'kev',         label: 'KEV',         explain: 'CISA Known Exploited Vulnerabilities — confirmed active exploitation in the wild.' },
  { id: 'critical',    label: 'CRITICAL',    explain: 'CVSS base score 9.0–10.0.' },
  { id: 'high',        label: 'HIGH',        explain: 'CVSS base score 7.0–8.9.' },
  { id: 'medium',      label: 'MEDIUM',      explain: 'CVSS base score 4.0–6.9.' },
  { id: 'poc',         label: 'PoC',         explain: 'CVEs with a public proof-of-concept exploit or reference.' },
  { id: 'kev_overdue', label: 'KEV OVERDUE', explain: 'KEV entries past their CISA federal remediation deadline. Prioritize if affected products are in your environment.' },
]

export const VENDORS = [
  'Adobe', 'Amazon', 'Apache', 'Apple', 'Atlassian', 'Check Point', 'Cisco',
  'Citrix', 'Dell', 'Docker', 'F5', 'Fortinet', 'GitLab', 'Google', 'HP',
  'IBM', 'Ivanti', 'Jenkins', 'Juniper', 'Kubernetes', 'Linux', 'Microsoft',
  'MongoDB', 'Node.js', 'Oracle', 'Palo Alto', 'PHP', 'Python', 'SAP',
  'Siemens', 'VMware', 'WordPress',
]

function deriveActive(filters) {
  if (filters.watchlist_only && !filters.kev_only && !filters.kev_overdue_only && !filters.poc_only && !filters.severity) {
    return 'watchlist'
  }
  if (filters.kev_overdue_only && !filters.kev_only && !filters.poc_only && !filters.severity) return 'kev_overdue'
  if (filters.kev_only && !filters.kev_overdue_only && !filters.poc_only && !filters.severity) return 'kev'
  if (filters.severity === 'CRITICAL' && !filters.kev_only && !filters.kev_overdue_only && !filters.poc_only) return 'critical'
  if (filters.severity === 'HIGH'     && !filters.kev_only && !filters.kev_overdue_only && !filters.poc_only) return 'high'
  if (filters.severity === 'MEDIUM'   && !filters.kev_only && !filters.kev_overdue_only && !filters.poc_only) return 'medium'
  if (filters.poc_only && !filters.kev_only && !filters.kev_overdue_only && !filters.severity) return 'poc'
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
    filters.kev_overdue_only ||
    filters.poc_only ||
    filters.patch_only ||
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
  feedListRef,
  feedCardCount = 0,
  onGenerateDigest,
  searchFocusTrigger,
  searchStatus = '',
}) {
  const [localSearch, setLocalSearch] = useState(filters.search || '')
  const [localStack, setLocalStack] = useState(() => filters.stack || '')
  const [stackHintVisible, setStackHintVisible] = useState(() => {
    try { return localStorage.getItem('briefr_stack_hint_dismissed') !== '1' } catch { return true }
  })
  const [exporting, setExporting] = useState(null)
  const [exportError, setExportError] = useState(null)
  const [exportSuccess, setExportSuccess] = useState(null)
  const [coverage, setCoverage] = useState(null)
  const [backfillRun, setBackfillRun] = useState(null)
  const [backfillBusy, setBackfillBusy] = useState(false)
  const [backfillError, setBackfillError] = useState(null)
  const debounceRef  = useRef(null)
  const stackDebounceRef = useRef(null)
  const exportSuccessTimeoutRef = useRef(null)
  const searchRef    = useRef(null)
  const pollRef = useRef(null)

  useEffect(() => {
    setLocalSearch(filters.search || '')
  }, [filters.search])

  useEffect(() => {
    setLocalStack((prev) => nextLocalStack(prev, filters.stack))
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

  useEffect(() => {
    let cancelled = false
    fetchStackCoverage()
      .then((body) => {
        if (!cancelled) setCoverage(body)
      })
      .catch(() => {
        if (!cancelled) setCoverage(null)
      })
    return () => { cancelled = true }
  }, [filters.stack, filters.my_stack_only])

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  function startBackfillPolling(runId) {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const st = await fetchStackBackfillRun(runId)
        setBackfillRun(st.run)
        if (['completed', 'partial', 'failed'].includes(st.run?.status)) {
          clearInterval(pollRef.current)
          pollRef.current = null
          const cov = await fetchStackCoverage().catch(() => null)
          if (cov) setCoverage(cov)
        }
      } catch {
        /* ignore poll blips */
      }
    }, 2000)
  }

  async function handleAgreeBackfill() {
    setBackfillBusy(true)
    setBackfillError(null)
    try {
      const body = await agreeStackBackfill()
      setBackfillRun({ id: body.run_id, status: 'pending', progress_message: body.message, ...body.eta })
      startBackfillPolling(body.run_id)
    } catch (e) {
      setBackfillError(e?.message || 'Could not start Tier A backfill')
    } finally {
      setBackfillBusy(false)
    }
  }

  async function handleResumeBackfill() {
    if (!backfillRun?.id) return
    setBackfillBusy(true)
    try {
      await resumeStackBackfill(backfillRun.id)
      const st = await fetchStackBackfillRun(backfillRun.id)
      setBackfillRun(st.run)
      startBackfillPolling(backfillRun.id)
    } catch (e) {
      setBackfillError(e?.message || 'Resume failed')
    } finally {
      setBackfillBusy(false)
    }
  }

  const active = deriveActive(filters)
  const selectedVendors = parseVendors(filters.vendors)

  function handleQuickFilter(id) {
    const base = {
      severity: null,
      kev_only: false,
      kev_overdue_only: false,
      poc_only: false,
      watchlist_only: false,
    }
    if (id === 'watchlist')     onFiltersChange({ ...base, watchlist_only: true })
    else if (id === 'kev')           onFiltersChange({ ...base, kev_only: true })
    else if (id === 'kev_overdue')   onFiltersChange({ ...base, kev_overdue_only: true })
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
      saveUserStack(trimmed).catch((err) => notifyApiError(err))
      onFiltersChange({ stack: trimmed })
    }, STACK_DEBOUNCE_MS)
  }

  function handleDismissStackHint() {
    try { localStorage.setItem('briefr_stack_hint_dismissed', '1') } catch { /* ignore */ }
    setStackHintVisible(false)
  }

  function handleStackClear() {
    setLocalStack('')
    if (stackDebounceRef.current) clearTimeout(stackDebounceRef.current)
    saveUserStack('').catch((err) => notifyApiError(err))
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
    notifyExportProgress('Preparing CSV export…')
    try {
      const rows = await fetchExportRows()
      downloadCsv(cvesToCsvRows(rows), exportFilename())
      const message = `Downloaded ${rows.length.toLocaleString()} CVEs as CSV.`
      showExportSuccess(message)
      notifyExportSuccess(message)
    } catch (err) {
      const message = err?.message || 'Export failed. Restart the backend and try again.'
      setExportError(message)
      notifyExportError(message)
    } finally {
      setExporting(null)
    }
  }

  async function handleExportXlsx() {
    if (exporting) return
    setExporting('xlsx')
    setExportError(null)
    setExportSuccess(null)
    notifyExportProgress('Preparing Excel export…')
    try {
      const rows = await fetchExportRows()
      const { downloadCvesXlsx, exportXlsxFilename } = await import('../utils/exportXlsx.js')
      await downloadCvesXlsx(rows, exportXlsxFilename())
      const message = `Downloaded ${rows.length.toLocaleString()} CVEs as Excel (.xlsx).`
      showExportSuccess(message)
      notifyExportSuccess(message)
    } catch (err) {
      const message = err?.message || 'Excel export failed. Restart the backend and try again.'
      setExportError(message)
      notifyExportError(message)
    } finally {
      setExporting(null)
    }
  }

  return (
    <div className="feed-controls">
      <div className="filter-toolbar-anchor">
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
                  {feedListRef && feedCardCount > 0 && (
                    <FeedVisibleRange
                      listRootRef={feedListRef}
                      cardCount={feedCardCount}
                    />
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

        <div className="filter-bar-stack control-toolbar--fields">
          <label className="control-field filter-stack-field" htmlFor="feed-stack-input">
            <span className="control-field-label filter-stack-label">STACK //</span>
            <span className="filter-stack-control">
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
            </span>
          </label>
        </div>

        {stackHintVisible && !localStack && (
          <div className="stack-hint" role="note" aria-label="Stack filter tip">
            <span className="stack-hint-text">
              <span className="stack-hint-label mono">MY STACK FILTER</span> narrows the feed to CVEs that mention technologies in your stack filter.
              Type products you run — e.g. <code>nginx, python, openssl</code> — or load My Stack from the header for version-aware matching.
            </span>
            <button
              type="button"
              className="stack-hint-dismiss mono"
              onClick={handleDismissStackHint}
              aria-label="Dismiss stack tip"
            >
              ×
            </button>
          </div>
        )}

        {coverage?.needs_backfill && (
          <div className="stack-gap-banner" role="status" aria-label="Stack corpus gap">
            <div className="stack-gap-banner-text">
              <span className="mono stack-hint-label">CORPUS GAP</span>
              {' '}
              Shallow history for {coverage.shallow_count} stack product(s).
              Tier A ETA ~{Math.round((coverage.eta?.eta_low_seconds || 0) / 60)}–
              {Math.round((coverage.eta?.eta_high_seconds || 0) / 60)} min
              {!coverage.eta?.has_nvd_key ? ' (anonymous NVD pacing — key recommended)' : ''}.
              Deep intel stays on background jobs.
            </div>
            <button
              type="button"
              className="filter-export-btn mono"
              disabled={backfillBusy}
              onClick={handleAgreeBackfill}
              aria-label="Agree to Tier A historical backfill"
            >
              {backfillBusy ? 'Starting…' : 'Agree — Tier A backfill'}
            </button>
          </div>
        )}
        {backfillError && (
          <p className="mono" style={{ color: 'var(--status-error)', fontSize: 'var(--font-size-xs)', margin: 0 }}>
            {backfillError}
          </p>
        )}
        {backfillRun && (
          <div className="stack-gap-banner" role="status" aria-label="Backfill progress">
            <div className="stack-gap-banner-text mono">
              Tier A [{backfillRun.status}] — {backfillRun.progress_message || 'Running…'}
              {backfillRun.cves_upserted != null ? ` · ${backfillRun.cves_upserted} CVEs` : ''}
            </div>
            {['deferred', 'on_hold', 'partial'].includes(backfillRun.status) && (
              <button
                type="button"
                className="filter-export-btn mono"
                disabled={backfillBusy}
                onClick={handleResumeBackfill}
              >
                Resume
              </button>
            )}
          </div>
        )}

        <div className="filter-bar-search-row">
          <input
            ref={searchRef}
            type="search"
            className="filter-search"
            value={localSearch}
            onChange={handleSearchChange}
            placeholder="search CVE-ID, keyword, or describe an issue…"
            aria-label="Search CVEs by ID, keyword, or natural language (press / to focus)"
            autoComplete="off"
            spellCheck="false"
          />
          {searchStatus && (filters.search || '').trim() && (
            <span className="filter-search-status mono" role="status">
              {searchStatus}
            </span>
          )}
        </div>

        <div className="filter-bar-filters">
          <div className="filter-buttons" role="group" aria-label="Quick filters">
            {QUICK_FILTERS.map(f => (
              <ControlTooltip key={f.id} text={f.explain}>
                <button
                  className={`filter-btn${active === f.id ? ' active' : ''}`}
                  onClick={() => handleQuickFilter(f.id)}
                  aria-label={`Filter: ${f.label}`}
                  aria-pressed={active === f.id}
                >
                  {f.label}
                </button>
              </ControlTooltip>
            ))}
          </div>
        </div>
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
        </div>
      </div>

      {(active === 'all' || selectedVendors.length > 0) && (
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
