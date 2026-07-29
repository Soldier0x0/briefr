import { useCallback, useRef, useState } from 'react'

export function useBusyGuard(cooldownMs = 5000) {
  const [busy, setBusy] = useState(false)
  const timerRef = useRef(null)

  const guard = useCallback(async (fn) => {
    if (busy) return undefined
    setBusy(true)
    try {
      return await fn()
    } finally {
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setBusy(false), cooldownMs)
    }
  }, [busy, cooldownMs])

  return { busy, guard }
}
