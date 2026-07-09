import { useState, useEffect, useCallback, useRef } from 'react'

/**
 * Async data hook with AbortController lifecycle and stale-while-revalidate.
 *
 * @param {(signal: AbortSignal) => Promise<*>} fn - Fetcher; receives the current abort signal.
 * @param {unknown[]} deps - Re-run when these change (same semantics as useEffect).
 * @returns {{ data: *, error: Error|null, loading: boolean, refreshing: boolean, retry: () => void }}
 */
export default function useAsync(fn, deps) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const dataRef = useRef(null)
  const fnRef = useRef(fn)

  fnRef.current = fn
  dataRef.current = data

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    const hasData = dataRef.current != null

    if (hasData) setRefreshing(true)
    else setLoading(true)

    ;(async () => {
      try {
        const result = await fnRef.current(controller.signal)
        if (cancelled || controller.signal.aborted) return
        setData(result)
        setError(null)
      } catch (err) {
        if (cancelled || controller.signal.aborted || err?.name === 'AbortError') return
        setError(err instanceof Error ? err : new Error(String(err?.message || err)))
      } finally {
        if (!cancelled) {
          setLoading(false)
          setRefreshing(false)
        }
      }
    })()

    return () => {
      cancelled = true
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps array is intentional API
  }, [...deps, retryCount])

  const retry = useCallback(() => setRetryCount(c => c + 1), [])

  return { data, error, loading, refreshing, retry }
}
