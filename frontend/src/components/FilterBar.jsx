import { useState, useRef, useEffect } from 'react'
import {
  agreeStackBackfill,
  fetchCVEsForExport,
  fetchStackBackfillRun,
  fetchStackCoverage,
  resumeStackBackfill,
} from '../api.js'
import { notifyExportError, notifyExportProgress, notifyExportSuccess } from './Toast.jsx'
import { toApiCveParams, filtersPatchChanged } from '../utils/cveFilters.js'
import { cvesToCsvRows, downloadCsv, exportFilename } from '../utils/exportCsv.js'
import { formatSectionHeading } from '../utils/sectionHeading.js'
import ControlTooltip from './ControlTooltip.jsx'
import FeedVisibleRange from './FeedVisibleRange.jsx'
import { nextLocalStack } from '../utils/stackLocalSync.js'
import {
  parseFeedQuery,
  parsedQueryToFilters,
} from '../utils/feedQueryParser.js'
import { VENDORS } from '../utils/vendorList.js'
import ParsedQueryChips from './ParsedQueryChips.jsx'
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

export { VENDORS } from '../utils/vendorList.js'

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
    (filters.feed_query && filters.feed_query.trim()) ||
    (filters.search && filters.search.trim()) ||
    filters.stack ||
    filters.technique ||
    filters.vendors ||
    filters.exclude_vendors ||
    filters.severity_list ||
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
  const [localSearch, setLocalSearch] = useState(filters.feed_query || filters.search || '')
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
      setBackfillError(e?.message || 'Could not start historical backfill')
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
  const parsedChips = filters.parsed_chips || []

  function applyParsedSearch(queryText) {
    const trimmed = String(queryText || '').trim()
    if (!trimmed) {
      onFiltersChange({
        feed_query: '',
        search: '',
        vendors: '',
        exclude_vendors: '',
        severity: null,
        severity_list: '',
        kev_only: false,
        kev_overdue_only: false,
        poc_only: false,
        patch_only: false,
        watchlist_only: false,
        epss_min: null,
        technique: '',
        published_on: '',
        parsed_chips: [],
      })
      return
    }
    const patch = parsedQueryToFilters(parseFeedQuery(trimmed))
    onFiltersChange({
      feed_query: trimmed,
      search: patch.search,
      vendors: patch.vendors,
      exclude_vendors: patch.exclude_vendors,
      severity: patch.severity,
      severity_list: patch.severity_list,
      kev_only: patch.kev_only,
      kev_overdue_only: patch.kev_overdue_only,
      poc_only: patch.poc_only,
      patch_only: patch.patch_only,
      watchlist_only: patch.watchlist_only,
      epss_min: patch.epss_min,
      technique: patch.technique,
      published_on: patch.published_on,
      parsed_chips: patch.parsed_chips,
      ...(patch.stack ? { stack: patch.stack } : {}),
    })
  }

  function clearSearchQueryState() {
    return {
      feed_query: '',
      search: '',
      parsed_chips: [],
      vendors: '',
      exclude_vendors: '',
      severity_list: '',
      technique: '',
      published_on: '',
      epss_min: null,
    }
  }

  function applyQuickFilter(patch) {
    setLocalSearch('')
    onFiltersChange({
      ...clearSearchQueryState(),
      kev_only: false,
      kev_overdue_only: false,
      poc_only: false,
      patch_only: false,
      watchlist_only: false,
      severity: null,
      ...patch,
    })
  }

  function handleQuickFilter(id) {
    if (id === 'all') {
      applyQuickFilter({})
      return
    }

    const active = deriveActive(filters)
    if (active === id) {
      applyQuickFilter({})
      return
    }

    switch (id) {
      case 'watchlist':
        applyQuickFilter({ watchlist_only: true })
        break
      case 'kev':
        applyQuickFilter({ kev_only: true })
        break
      case 'kev_overdue':
        applyQuickFilter({ kev_overdue_only: true })
        break
      case 'critical':
        applyQuickFilter({ severity: 'CRITICAL' })
        break
      case 'high':
        applyQuickFilter({ severity: 'HIGH' })
        break
      case 'medium':
        applyQuickFilter({ severity: 'MEDIUM' })
        break
      case 'poc':
        applyQuickFilter({ poc_only: true })
        break
      default:
        break
    }
  }

  function handleSearchChange(e) {
    const val = e.target.value
    setLocalSearch(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      applyParsedSearch(val)
    }, 320)
  }

  function handleParsedQueryChange(nextQuery) {
    setLocalSearch(nextQuery)
    applyParsedSearch(nextQuery)
  }

  function handleStackChange(e) {
    const val = e.target.value
    setLocalStack(val)
    if (stackDebounceRef.current) clearTimeout(stackDebounceRef.current)
    stackDebounceRef.current = setTimeout(() => {
      const trimmed = val.trim()
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
    onFiltersChange({ stack: '' })
  }

  function handleVendorClick(vendor) {
    const token = vendor.toLowerCase()
    const nextSearch = selectedVendors.includes(vendor)
      ? localSearch.replace(new RegExp(`\\b${token}\\b`, 'gi'), '').replace(/\s+/g, ' ').trim()
      : (localSearch.trim() ? `${localSearch.trim()} ${token}` : token)
    setLocalSearch(nextSearch)
    applyParsedSearch(nextSearch)
  }

  function clearVendors() {
    const nextSearch = localSearch
      .split(/\s+/)
      .filter((part) => !VENDORS.some((v) => v.toLowerCase() === part.toLowerCase()))
      .join(' ')
      .trim()
    setLocalSearch(nextSearch)
    applyParsedSearch(nextSearch)
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
            <span className="control-field-label filter-stack-label">{formatSectionHeading('STACK //')}</span>
            <span className="filter-stack-control">
              <input
                id="feed-stack-input"
                type="text"
                className="filter-stack-input"
                value={localStack}
                onChange={handleStackChange}
                placeholder="nginx, python, linux kernel..."
                aria-label="Enter throwaway stack terms to filter the CVE feed"
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
              Type products to narrow this feed view — e.g. <code>nginx, python, openssl</code>. This filter is throwaway and does not save My Stack. Use the header Asset wizard for alerts.
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
              Historical backfill ETA ~{Math.round((coverage.eta?.eta_low_seconds || 0) / 60)}–
              {Math.round((coverage.eta?.eta_high_seconds || 0) / 60)} min
              {!coverage.eta?.has_nvd_key ? ' (anonymous NVD pacing — key recommended)' : ''}.
              Deep intel stays on background jobs.
            </div>
            <button
              type="button"
              className="filter-export-btn mono"
              disabled={backfillBusy}
              onClick={handleAgreeBackfill}
              aria-label="Agree to historical backfill"
            >
              {backfillBusy ? 'Starting…' : 'Agree — historical backfill'}
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
              Historical backfill [{backfillRun.status}] — {backfillRun.progress_message || 'Running…'}
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
            placeholder="search: amazon + kev, vendor:apache is:kev, &quot;log4j&quot;…"
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

        <ParsedQueryChips
          chips={parsedChips}
          query={localSearch}
          onQueryChange={handleParsedQueryChange}
        />

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

      <div className="vendor-filter-block">
          <div className="vendor-filter-header">
            <span className="vendor-filter-label mono">{formatSectionHeading('// COMMON VENDORS')}</span>
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
    </div>
  )
}
