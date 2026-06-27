import { useEffect, useRef } from 'react'

const IDLE_MS = 30 * 60 * 1000
const WARN_MS = 25 * 60 * 1000
const HIDDEN_MS = 30 * 60 * 1000
const TICK_MS = 60 * 1000

/**
 * Clears My Stack when idle (30m) or tab hidden (30m).
 * lastInteraction stored in ref only — no re-renders on activity.
 */
export function useInactivityTimeout({ enabled, onTimeout, onWarning }) {
  const lastInteractionRef = useRef(Date.now())
  const hiddenSinceRef = useRef(null)
  const warnedRef = useRef(false)

  useEffect(() => {
    if (!enabled) return undefined

    const touch = () => {
      lastInteractionRef.current = Date.now()
      warnedRef.current = false
    }

    const events = ['mousedown', 'keydown', 'scroll', 'touchstart']
    events.forEach(ev => window.addEventListener(ev, touch, { passive: true }))

    const onVisibility = () => {
      if (document.hidden) {
        hiddenSinceRef.current = Date.now()
      } else {
        hiddenSinceRef.current = null
        touch()
      }
    }
    document.addEventListener('visibilitychange', onVisibility)

    const interval = setInterval(() => {
      const now = Date.now()
      if (document.hidden && hiddenSinceRef.current) {
        if (now - hiddenSinceRef.current >= HIDDEN_MS) {
          onTimeout()
          hiddenSinceRef.current = now
        }
        return
      }
      if (now - lastInteractionRef.current >= IDLE_MS) {
        onTimeout()
        lastInteractionRef.current = now
        return
      }
      if (onWarning && !warnedRef.current && now - lastInteractionRef.current >= WARN_MS) {
        warnedRef.current = true
        onWarning()
      }
    }, TICK_MS)

    return () => {
      events.forEach(ev => window.removeEventListener(ev, touch))
      document.removeEventListener('visibilitychange', onVisibility)
      clearInterval(interval)
    }
  }, [enabled, onTimeout, onWarning])
}
