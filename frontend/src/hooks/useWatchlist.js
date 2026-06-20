import { useCallback, useEffect, useRef, useState } from 'react'
import { clearAllSnoozes, fetchWatchlist, removeWatchlistEntry, setWatchlistEntry } from '../api.js'

function normalizeCveId(cveId) {
  return cveId ? cveId.toUpperCase() : cveId
}

/**
 * Server-backed CVE watchlist (pin only in UI). Snooze was removed from the
 * product surface — any legacy snooze rows are cleared once on first load.
 */
export function useWatchlist() {
  const [byCveId, setByCveId] = useState({})
  const [version, setVersion] = useState(0)
  const mountedRef = useRef(true)
  const snoozesClearedRef = useRef(false)

  const applyEntries = useCallback((entries) => {
    const next = {}
    for (const row of entries || []) {
      if (row?.cve_id && row.state === 'pin') {
        next[normalizeCveId(row.cve_id)] = row
      }
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
    let cancelled = false

    async function bootstrap() {
      if (!snoozesClearedRef.current) {
        try {
          await clearAllSnoozes()
          snoozesClearedRef.current = true
        } catch {
          // Non-fatal — pins still work; snoozed rows may linger until manual clear.
        }
      }
      if (!cancelled) await refresh()
    }

    bootstrap()
    return () => {
      cancelled = true
      mountedRef.current = false
    }
  }, [refresh])

  const bump = useCallback(() => {
    setVersion(v => v + 1)
  }, [])

  const pin = useCallback(async (cveId) => {
    const key = normalizeCveId(cveId)
    const data = await setWatchlistEntry(cveId, 'pin')
    if (!mountedRef.current) return data
    setByCveId(prev => ({ ...prev, [key]: data.data }))
    bump()
    return data
  }, [bump])

  const remove = useCallback(async (cveId) => {
    const key = normalizeCveId(cveId)
    await removeWatchlistEntry(cveId)
    if (!mountedRef.current) return
    setByCveId(prev => {
      const next = { ...prev }
      delete next[key]
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

  return {
    byCveId,
    version,
    refresh,
    pin,
    remove,
    togglePin,
    getState: (cveId) => {
      if (!cveId) return null
      return byCveId[cveId.toUpperCase()]?.state || null
    },
  }
}
