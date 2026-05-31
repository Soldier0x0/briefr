import { useState, useEffect, useRef, useCallback } from 'react'
import { fetchCVEs } from '../api.js'
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

export default function CVEFeed({ filters, onFiltersChange, onSelectCVE, onGenerateDigest, searchFocusTrigger }) {
  const [cves, setCves] = useState([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [hasMore, setHasMore] = useState(true)
  const sentinelRef = useRef(null)
  const abortRef = useRef(null)

  const load = useCallback(async (currentPage, currentFilters, append) => {
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)

    try {
      const data = await fetchCVEs({
        ...currentFilters,
        page: currentPage,
        limit: PAGE_LIMIT,
      })

      if (controller.signal.aborted) return

      setTotal(data.total)
      setHasMore(currentPage < data.pages)
      setCves(prev => append ? [...prev, ...data.data] : data.data)
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err.message)
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [])

  // Reset and reload when filters change
  useEffect(() => {
    setPage(1)
    setCves([])
    setHasMore(true)
    load(1, filters, false)
  }, [filters, load])

  // Load next page when page increments beyond 1
  useEffect(() => {
    if (page > 1) {
      load(page, filters, true)
    }
  }, [page]) // eslint-disable-line react-hooks/exhaustive-deps

  // Infinite scroll via IntersectionObserver
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loading && hasMore) {
          setPage(p => p + 1)
        }
      },
      { rootMargin: '200px' }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [loading, hasMore])

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
        {cves.map(cve => (
          <CVECard
            key={cve.cve_id}
            cve={cve}
            onSelect={onSelectCVE}
          />
        ))}
      </div>

      {/* Infinite scroll sentinel */}
      <div ref={sentinelRef} className="scroll-sentinel" aria-hidden="true" />

      {/* Loading more indicator */}
      {loading && cves.length > 0 && (
        <div className="feed-loading-more" aria-live="polite" aria-label="Loading more CVEs">
          <span className="loading-dots" aria-hidden="true">
            <span /><span /><span />
          </span>
        </div>
      )}

      {/* End of feed */}
      {!hasMore && cves.length > 0 && (
        <div className="feed-end" aria-label="End of results">
          <span>// {cves.length} of {total} shown</span>
        </div>
      )}
    </div>
  )
}
