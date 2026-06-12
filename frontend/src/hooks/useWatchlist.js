import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchWatchlist, removeWatchlistEntry, setWatchlistEntry } from '../api.js'

const DEFAULT_SNOOZE_DAYS = 7

/**
 * Server-backed CVE watchlist (pin / snooze). Single-user — no localStorage.
 * `version` bumps after mutations so the feed can refetch ordering/filters.
 */
export function useWatchlist() {
  const [byCveId, setByCveId] = useState({})
  const [version, setVersion] = useState(0)
  const mountedRef = useRef(true)

  const applyEntries = useCallback((entries) => {
    const next = {}
    for (const row of entries || []) {
      if (row?.cve_id) next[row.cve_id] = row
    }
    setByCveId(next)
  }, [])

  const refresh = useCallback(async () => {
    try {
      const data = await fetchWatchlist()
      if (!mountedRef.current) return
      applyEntries(data.data)
    } catch {
      // Feed still works without watchlist metadata.
    }
  }, [applyEntries])

  useEffect(() => {
    mountedRef.current = true
    refresh()
    return () => {
      mountedRef.current = false
    }
  }, [refresh])

  const bump = useCallback(() => {
    setVersion(v => v + 1)
  }, [])

  const pin = useCallback(async (cveId) => {
    const data = await setWatchlistEntry(cveId, 'pin')
    if (!mountedRef.current) return data
    setByCveId(prev => ({ ...prev, [cveId]: data.data }))
    bump()
    return data
  }, [bump])

  const snooze = useCallback(async (cveId, days = DEFAULT_SNOOZE_DAYS) => {
    const data = await setWatchlistEntry(cveId, 'snooze', days)
    if (!mountedRef.current) return data
    setByCveId(prev => ({ ...prev, [cveId]: data.data }))
    bump()
    return data
  }, [bump])

  const remove = useCallback(async (cveId) => {
    await removeWatchlistEntry(cveId)
    if (!mountedRef.current) return
    setByCveId(prev => {
      const next = { ...prev }
      delete next[cveId]
      return next
    })
    bump()
  }, [bump])

  const togglePin = useCallback(async (cveId, currentState) => {
    if (currentState === 'pin') {
      await remove(cveId)
    } else {
      await pin(cveId)
    }
  }, [pin, remove])

  const toggleSnooze = useCallback(async (cveId, currentState) => {
    if (currentState === 'snooze') {
      await remove(cveId)
    } else {
      await snooze(cveId)
    }
  }, [snooze, remove])

  return {
    byCveId,
    version,
    refresh,
    pin,
    snooze,
    remove,
    togglePin,
    toggleSnooze,
    getState: (cveId) => {
      if (!cveId) return null
      return byCveId[cveId.toUpperCase()]?.state || null
    },
  }
}
