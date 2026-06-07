import { useState, useEffect, useRef, useCallback } from 'react'
import { fetchCVEs } from '../api.js'
import { toApiCveParams } from '../utils/cveFilters.js'
import { buildCombinedReport, copyToClipboard } from '../utils/report.js'
import { downloadBulkCvePdf } from '../utils/pdfReport.js'
import PdfExportModal from './PdfExportModal.jsx'
import FilterBar from './FilterBar.jsx'
import CVECard from './CVECard.jsx'
import ScrollToTop from './ScrollToTop.jsx'
import { useInvestigationOptional } from '../context/InvestigationContext.jsx'
import { useAssetProfileOptional } from '../context/AssetProfileContext.jsx'
import { calculateRiskScore } from '../scoring/riskScore.js'
import './CVEFeed.css'

const PAGE_LIMIT = 20
const LAST_VISIT_KEY = 'briefr_last_visit'

function SkeletonCard() {
  return (
    <div className="skeleton-card" aria-hidden="true">
      <div className="sk sk-id" />
      <div className="sk sk-line" />
      <div className="sk sk-line sk-short" />
      <div className="sk sk-meta" />
    </div>
  )
}

function sortByExposure(cves, getMatchScore) {
  return [...cves].sort((a, b) => {
    const diff = getMatchScore(b.cve_id) - getMatchScore(a.cve_id)
    if (diff !== 0) return diff
    return (b.cvss_score ?? 0) - (a.cvss_score ?? 0)
  })
}

export default function CVEFeed({ filters, onFiltersChange, onSelectCVE, onGenerateDigest, onDigestRequest, searchFocusTrigger, timezone }) {
  const investigation = useInvestigationOptional()
  const assetCtx = useAssetProfileOptional()
  const assetAware = Boolean(assetCtx?.isLoaded)
  const getMatchScore = assetCtx?.getMatchScore ?? (() => 0)
  const assetAwareRef = useRef(assetAware)
  const getMatchScoreRef = useRef(getMatchScore)
  assetAwareRef.current = assetAware
  getMatchScoreRef.current = getMatchScore
  const [cves, setCves] = useState([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(null)
  const [loading, setLoading] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [error, setError] = useState(null)
  const [hasMore, setHasMore] = useState(true)
  const [selectedMap, setSelectedMap] = useState({})
  const [copyAllState, setCopyAllState] = useState('idle')
  const [bulkMenuOpen, setBulkMenuOpen] = useState(false)
  const [bulkPdfModalOpen, setBulkPdfModalOpen] = useState(false)
  const [bulkPdfBusy, setBulkPdfBusy] = useState(false)
  const bulkMenuRef = useRef(null)
  const [selectedIndex, setSelectedIndex] = useState(null)
  const [lastVisit, setLastVisit] = useState(null)
  const [visitReady, setVisitReady] = useState(false)
  const [showingRange, setShowingRange] = useState(null)
  const sentinelRef = useRef(null)
  const abortRef = useRef(null)
  const cardRefs = useRef([])
  const pageRef = useRef(1)
  const filtersRef = useRef(filters)
  const loadingRef = useRef(false)
  const isLoadingMoreRef = useRef(false)
  const hasMoreRef = useRef(true)
  const initialLoadDoneRef = useRef(false)
  const sentinelVisibleRef = useRef(false)
  const filtersInitialMountRef = useRef(true)

  useEffect(() => {
    let stored = null
    try {
      const raw = localStorage.getItem(LAST_VISIT_KEY)
      if (raw) stored = new Date(raw)
    } catch {}
    setLastVisit(stored)
    setVisitReady(true)
    try {
      localStorage.setItem(LAST_VISIT_KEY, new Date().toISOString())
    } catch {}
  }, [])

  // Keep Hero/stack visible on first paint; avoid browser scroll restoration
  useEffect(() => {
    const prev = history.scrollRestoration
    history.scrollRestoration = 'manual'
    window.scrollTo(0, 0)
    return () => {
      history.scrollRestoration = prev
    }
  }, [])

  function isNewSinceVisit(cve) {
    if (!visitReady || !lastVisit || !cve.published) return false
    return new Date(cve.published) > lastVisit
  }

  filtersRef.current = filters
  loadingRef.current = loading
  isLoadingMoreRef.current = isLoadingMore
  hasMoreRef.current = hasMore

  const updateShowingRange = useCallback(() => {
    const cards = cardRefs.current.filter(Boolean)
    if (!cards.length) {
      setShowingRange(null)
      return
    }

    const viewportH = window.innerHeight
    let first = null
    let last = null

    cards.forEach((el, idx) => {
      const rect = el.getBoundingClientRect()
      if (rect.bottom > 0 && rect.top < viewportH) {
        if (first === null) first = idx
        last = idx
      }
    })

    if (first === null) {
      first = 0
      last = Math.min(cards.length - 1, 0)
    }

    setShowingRange({ start: first + 1, end: last + 1 })
  }, [])

  const loadPage = useCallback(async (pageNum, append) => {
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    if (append) {
      setIsLoadingMore(true)
    } else {
      setLoading(true)
    }
    setError(null)

    try {
      const data = await fetchCVEs({
        ...toApiCveParams(filtersRef.current),
        page: pageNum,
        limit: PAGE_LIMIT,
      })

      if (controller.signal.aborted) return

      setTotal(data.total)
      const nextHasMore = pageNum < data.pages && data.data.length > 0
      setHasMore(nextHasMore)
      hasMoreRef.current = nextHasMore
      const pageRows = assetAwareRef.current
        ? sortByExposure(data.data, getMatchScoreRef.current)
        : data.data
      setCves(prev => {
        const next = append ? [...prev, ...pageRows] : pageRows
        requestAnimationFrame(() => updateShowingRange())
        return next
      })
      pageRef.current = pageNum
      setPage(pageNum)
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err.message)
      }
    } finally {
      if (!controller.signal.aborted) {
        if (append) {
          setIsLoadingMore(false)
        } else {
          setLoading(false)
          initialLoadDoneRef.current = true
        }
      }
    }
  }, [updateShowingRange])

  const loadNextPage = useCallback(() => {
    if (
      loadingRef.current ||
      isLoadingMoreRef.current ||
      !hasMoreRef.current ||
      !initialLoadDoneRef.current
    ) {
      return
    }
    loadPage(pageRef.current + 1, true)
  }, [loadPage])

  useEffect(() => {
    if (!onDigestRequest) return
    onDigestRequest(() => {
      if (onGenerateDigest && cves.length) onGenerateDigest(cves)
    })
  }, [onDigestRequest, onGenerateDigest, cves])

  useEffect(() => {
    updateShowingRange()
    window.addEventListener('scroll', updateShowingRange, { passive: true })
    window.addEventListener('resize', updateShowingRange, { passive: true })
    return () => {
      window.removeEventListener('scroll', updateShowingRange)
      window.removeEventListener('resize', updateShowingRange)
    }
  }, [cves, updateShowingRange])

  function scrollFeedToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  useEffect(() => {
    if (!assetAware || !cves.length) return
    setCves(prev => sortByExposure(prev, getMatchScore))
  }, [assetCtx?.matchScores, assetAware])

  // Reset and reload when filters change; scroll to page top (keeps Hero/stack visible)
  useEffect(() => {
    pageRef.current = 1
    setPage(1)
    setCves([])
    setHasMore(true)
    hasMoreRef.current = true
    setSelectedMap({})
    setSelectedIndex(null)
    initialLoadDoneRef.current = false
    sentinelVisibleRef.current = false
    setShowingRange(null)

    if (filtersInitialMountRef.current) {
      filtersInitialMountRef.current = false
    } else {
      scrollFeedToTop()
    }

    loadPage(1, false)
  }, [filters, loadPage])

  // Arrow-key card navigation (inactive while search is focused)
  useEffect(() => {
    function handleNav(e) {
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (!cves.length) return

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex(prev => {
          const next = prev === null ? 0 : Math.min(prev + 1, cves.length - 1)
          cardRefs.current[next]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
          return next
        })
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex(prev => {
          const next = prev === null ? 0 : Math.max(prev - 1, 0)
          cardRefs.current[next]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
          return next
        })
      } else if (e.key === 'Enter' && selectedIndex !== null && cves[selectedIndex]) {
        onSelectCVE(cves[selectedIndex])
      } else if (e.key === 'Escape' && selectedIndex !== null) {
        setSelectedIndex(null)
      }
    }
    document.addEventListener('keydown', handleNav)
    return () => document.removeEventListener('keydown', handleNav)
  }, [cves, selectedIndex, onSelectCVE])

  // Infinite scroll: stable observer (refs only — do not depend on loading state)
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries[0].isIntersecting
        const wasVisible = sentinelVisibleRef.current
        sentinelVisibleRef.current = visible

        // Edge-trigger: load only when sentinel enters view, not on every re-observe
        if (visible && !wasVisible) {
          loadNextPage()
        }
      },
      { root: null, rootMargin: '0px', threshold: 0 }
    )

    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [loadNextPage])

  function handleToggleSelect(cve) {
    setSelectedMap(prev => {
      const next = { ...prev }
      if (next[cve.cve_id]) {
        delete next[cve.cve_id]
      } else {
        next[cve.cve_id] = cve
      }
      return next
    })
  }

  useEffect(() => {
    if (!bulkMenuOpen) return
    function onDocClick(e) {
      if (bulkMenuRef.current && !bulkMenuRef.current.contains(e.target)) {
        setBulkMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [bulkMenuOpen])

  async function handleCopyAll() {
    const selected = Object.values(selectedMap)
    if (!selected.length) return
    const ok = await copyToClipboard(buildCombinedReport(selected))
    if (ok) {
      setCopyAllState('copied')
      setBulkMenuOpen(false)
      setTimeout(() => setCopyAllState('idle'), 2000)
    }
  }

  function handleBulkPdfClick() {
    setBulkMenuOpen(false)
    setBulkPdfModalOpen(true)
  }

  async function handleBulkPdfConfirm({ analystName }) {
    const selected = Object.values(selectedMap)
    if (!selected.length) return
    setBulkPdfBusy(true)
    try {
      await downloadBulkCvePdf(selected, { analystName })
      setBulkPdfModalOpen(false)
    } catch (err) {
      console.error('Bulk PDF failed:', err)
    } finally {
      setBulkPdfBusy(false)
    }
  }

  const selectedIds = Object.keys(selectedMap)
  const selectedCount = selectedIds.length

  const showSkeleton = loading && cves.length === 0
  const showEmpty = !loading && !error && cves.length === 0
  const showError = !!error && cves.length === 0

  return (
    <div className="cve-feed" role="region" aria-label="CVE feed">
      <FilterBar
        filters={filters}
        onFiltersChange={onFiltersChange}
        total={total}
        showingRange={showingRange}
        onGenerateDigest={() => onGenerateDigest && onGenerateDigest(cves)}
        searchFocusTrigger={searchFocusTrigger}
      />
      <ScrollToTop />

      {showError && (
        <div className="feed-state feed-error" role="alert">
          <span className="feed-state-icon" aria-hidden="true">!</span>
          <span>Failed to load CVEs: {error}</span>
        </div>
      )}

      {showEmpty && (
        <div className="feed-state feed-empty" role="status">
          <span className="feed-state-icon" aria-hidden="true">0</span>
          <span>No results for your filters.</span>
          <button
            className="feed-clear-btn"
            onClick={() => onFiltersChange({
              severity: null,
              kev_only: false,
              poc_only: false,
              search: '',
              epss_min: null,
              vendors: '',
              my_stack_only: false,
              summary_only: false,
            })}
            aria-label="Clear all filters"
          >
            Clear filters
          </button>
        </div>
      )}

      {showSkeleton && (
        <div aria-label="Loading CVEs" aria-busy="true">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      <div aria-live="polite" aria-atomic="false" className="cve-list">
        {cves.map((cve, idx) => (
          <CVECard
            key={cve.cve_id}
            cve={cve}
            onSelect={onSelectCVE}
            selected={!!selectedMap[cve.cve_id]}
            onToggleSelect={handleToggleSelect}
            timezone={timezone || 'UTC'}
            navSelected={selectedIndex === idx}
            isNew={isNewSinceVisit(cve)}
            cardRef={el => { cardRefs.current[idx] = el }}
            inThread={investigation?.isCveInThread?.(cve.cve_id)}
            onInvestigate={
              investigation
                ? (c) => investigation.startInvestigation(c)
                : undefined
            }
            onLookupIoc={
              investigation
                ? (c) => investigation.pivotToIocFromCve(c)
                : undefined
            }
            exposureScore={assetAware ? getMatchScore(cve.cve_id) : 0}
            riskScore={calculateRiskScore(cve, assetCtx?.profile ?? null)}
          />
        ))}
      </div>

      <div ref={sentinelRef} className="scroll-sentinel" aria-hidden="true" />

      {isLoadingMore && (
        <div className="feed-loading-more" aria-live="polite" aria-label="Loading more CVEs">
          <span className="loading-dots" aria-hidden="true">
            <span /><span /><span />
          </span>
        </div>
      )}

      {!hasMore && cves.length > 0 && (
        <div className="feed-end" aria-label="End of results">
          <span>// {cves.length} of {total} shown</span>
        </div>
      )}

      {selectedCount > 0 && (
        <div
          className="float-action-bar"
          role="toolbar"
          aria-label={`${selectedCount} CVEs selected`}
          aria-live="polite"
        >
          <span className="float-count mono">
            {selectedCount} selected
          </span>
          <div className="float-actions">
            <div className="float-report-wrap" ref={bulkMenuRef}>
              <button
                type="button"
                className={`float-btn float-btn-primary${copyAllState === 'copied' ? ' copied' : ''}`}
                onClick={() => setBulkMenuOpen(o => !o)}
                aria-expanded={bulkMenuOpen}
                aria-haspopup="menu"
                aria-label={`Report actions for ${selectedCount} selected CVEs`}
              >
                {copyAllState === 'copied' ? `Copied ${selectedCount}` : 'COPY ALL REPORTS ▾'}
              </button>
              {bulkMenuOpen && (
                <div className="float-report-menu" role="menu">
                  <button
                    type="button"
                    role="menuitem"
                    className="float-report-item mono"
                    onClick={handleBulkPdfClick}
                  >
                    Download PDF
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className="float-report-item mono"
                    onClick={handleCopyAll}
                  >
                    Copy Markdown
                  </button>
                </div>
              )}
            </div>
            <button
              className="float-btn"
              onClick={() => setSelectedMap({})}
              aria-label="Clear all selections"
            >
              CLEAR
            </button>
          </div>
        </div>
      )}

      <PdfExportModal
        open={bulkPdfModalOpen}
        title={`Bulk PDF — ${selectedCount} CVE${selectedCount === 1 ? '' : 's'}`}
        busy={bulkPdfBusy}
        onConfirm={handleBulkPdfConfirm}
        onCancel={() => !bulkPdfBusy && setBulkPdfModalOpen(false)}
      />
    </div>
  )
}
