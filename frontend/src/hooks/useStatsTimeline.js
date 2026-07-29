import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchStatsTimeline } from '../api.js'

const cache = new Map()

function cacheKey(days) {
  return `timeline:${days}`
}

function getCached(days) {
  const hit = cache.get(cacheKey(days))
  if (!hit) return null
  if (Date.now() - hit.at > hit.ttlMs) {
    cache.delete(cacheKey(days))
    return null
  }
  return hit.data
}

function setCached(days, data, ttlMs = 5 * 60 * 1000) {
  cache.set(cacheKey(days), { data, at: Date.now(), ttlMs })
}

/**
 * Shared stats timeline fetch — deduplicates requests for the same day window.
 *
 * @param {number} days
 * @param {{ enabled?: boolean, ttlMs?: number }} [options]
 */
export function useStatsTimeline(days, options = {}) {
  const { enabled = true, ttlMs } = options
  const [data, setData] = useState(() => (enabled ? getCached(days) : null))
  const [loading, setLoading] = useState(() => enabled && !getCached(days))
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)
  const cancelRef = useRef(null)

  const reload = useCallback((useCache = true) => {
    if (!enabled) return undefined

    if (cancelRef.current) {
      cancelRef.current()
      cancelRef.current = null
    }

    if (useCache) {
      const hit = getCached(days)
      if (hit) {
        setData(hit)
        setLoading(false)
        setError(null)
        setErrorRequestId(null)
        return undefined
      }
    }

    let cancelled = false
    cancelRef.current = () => {
      cancelled = true
    }
    setLoading(true)
    setError(null)
    setErrorRequestId(null)

    fetchStatsTimeline(days)
      .then((rows) => {
        if (cancelled) return
        const timeline = Array.isArray(rows) ? rows : []
        setCached(days, timeline, ttlMs)
        setData(timeline)
      })
      .catch((err) => {
        if (cancelled) return
        setData([])
        setError(err?.message || 'Failed to load activity timeline.')
        setErrorRequestId(err?.requestId || null)
        throw err
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
        if (cancelRef.current) cancelRef.current = null
      })

    return () => {
      cancelled = true
    }
  }, [days, enabled, ttlMs])

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return undefined
    }
    const cleanup = reload(true)
    return () => {
      if (cleanup) cleanup()
      if (cancelRef.current) {
        cancelRef.current()
        cancelRef.current = null
      }
    }
  }, [enabled, reload])

  return {
    timeline: data || [],
    loading,
    error,
    errorRequestId,
    reload,
  }
}

/** Test helper — clear module cache between tests. */
export function clearStatsTimelineCache() {
  cache.clear()
}
