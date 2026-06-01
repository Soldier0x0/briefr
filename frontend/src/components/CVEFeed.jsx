import { useState, useEffect, useRef, useCallback } from 'react'
import { fetchCVEs } from '../api.js'
import { buildCombinedReport, copyToClipboard } from '../utils/report.js'
import FilterBar from './FilterBar.jsx'
import CVECard from './CVECard.jsx'
import './CVEFeed.css'

const PAGE_LIMIT = 20

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

export default function CVEFeed({ filters, onFiltersChange, onSelectCVE, onGenerateDigest, searchFocusTrigger, timezone }) {
  const [cves, setCves] = useState([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [hasMore, setHasMore] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [selectedMap, setSelectedMap] = useState({})
  const [copyAllState, setCopyAllState] = useState('idle')
  const [navIndex, setNavIndex] = useState(null)
  const sentinelRef = useRef(null)
  const abortRef = useRef(null)
  const cardRefs = useRef([])
  const filtersRef = useRef(filters)
  const pageRef = useRef(1)
  const isLoadingMoreRef = useRef(false)
  const hasMoreRef = useRef(true)

  filtersRef.current = filters
  isLoadingMoreRef.current = isLoadingMore
  hasMoreRef.current = hasMore

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
        ...filtersRef.current,
        page: pageNum,
        limit: PAGE_LIMIT,
      })

      if (controller.signal.aborted) return

      setTotal(data.total)
      setHasMore(data.data.length >= PAGE_LIMIT)
      setCves(prev => (append ? [...prev, ...data.data] : data.data))
      pageRef.current = pageNum
      setPage(pageNum)
    } catch (err) {
      if (!controller.signal.aborted) {
        if (!append) setError(err.message)
      }
    } finally {
      if (!controller.signal.aborted) {
        if (append) {
          setIsLoadingMore(false)
        } else {
          setLoading(false)
        }
      }
    }
  }, [])

  // On mount / filter change: fetch only page 1
  useEffect(() => {
    pageRef.current = 1
    setPage(1)
    setCves([])
    setHasMore(true)
    setSelectedMap({})
    setNavIndex(null)
    loadPage(1, false)
  }, [filters, loadPage])

  useEffect(() => {
    function handleNav(e) {
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (!cves.length) return

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setNavIndex(prev => {
          const next = prev === null ? 0 : Math.min(prev + 1, cves.length - 1)
          cardRefs.current[next]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
          return next
        })
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setNavIndex(prev => {
          const next = prev === null ? 0 : Math.max(prev - 1, 0)
          cardRefs.current[next]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
          return next
        })
      } else if (e.key === 'Enter' && navIndex !== null && cves[navIndex]) {
        onSelectCVE(cves[navIndex])
      } else if (e.key === 'Escape' && navIndex !== null) {
        setNavIndex(null)
      }
    }
    document.addEventListener('keydown', handleNav)
    return () => document.removeEventListener('keydown', handleNav)
  }, [cves, navIndex, onSelectCVE])

  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return
        if (isLoadingMoreRef.current || !hasMoreRef.current) return

        const nextPage = pageRef.current + 1
        loadPage(nextPage, true)
      },
      { rootMargin: '200px' }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [loadPage])

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

  async function handleCopyAll() {
    const selected = Object.values(selectedMap)
    if (!selected.length) return
    const ok = await copyToClipboard(buildCombinedReport(selected))
    if (ok) {
      setCopyAllState('copied')
      setTimeout(() => setCopyAllState('idle'), 2000)
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
        onGenerateDigest={() => onGenerateDigest && onGenerateDigest(cves)}
        searchFocusTrigger={searchFocusTrigger}
      />

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
            onClick={() => onFiltersChange({ severity: null, kev_only: false, poc_only: false, search: '', epss_min: null })}
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
            navSelected={navIndex === idx}
            cardRef={el => { cardRefs.current[idx] = el }}
          />
        ))}
      </div>

      <div ref={sentinelRef} style={{ height: '1px' }} />

      {isLoadingMore && cves.length > 0 && (
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
            <button
              className={`float-btn float-btn-primary${copyAllState === 'copied' ? ' copied' : ''}`}
              onClick={handleCopyAll}
              aria-label={`Copy combined report for all ${selectedCount} selected CVEs`}
            >
              {copyAllState === 'copied' ? `Copied ${selectedCount} reports` : 'COPY ALL REPORTS'}
            </button>
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
    </div>
  )
}
