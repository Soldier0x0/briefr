import { useEffect, useRef } from 'react'

const IDLE_MS = 30 * 60 * 1000
const HIDDEN_MS = 10 * 60 * 1000
const TICK_MS = 60 * 1000

/**
 * Clears profile when idle (30m) or tab hidden (10m).
 * lastInteraction stored in ref only — no re-renders on activity.
 */
export function useInactivityTimeout({ enabled, onTimeout }) {
  const lastInteractionRef = useRef(Date.now())
  const hiddenSinceRef = useRef(null)

  useEffect(() => {
    if (!enabled) return undefined

    const touch = () => {
      lastInteractionRef.current = Date.now()
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
      }
    }, TICK_MS)

    return () => {
      events.forEach(ev => window.removeEventListener(ev, touch))
      document.removeEventListener('visibilitychange', onVisibility)
      clearInterval(interval)
    }
  }, [enabled, onTimeout])
}
