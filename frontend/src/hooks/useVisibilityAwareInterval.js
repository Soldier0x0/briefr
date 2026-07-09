import { useEffect, useRef } from 'react'

/**
 * Interval that pauses when the document is hidden or ``enabled`` is false.
 *
 * @param {() => void} callback
 * @param {number | null} delayMs
 * @param {{ enabled?: boolean }} [options]
 */
export default function useVisibilityAwareInterval(callback, delayMs, options = {}) {
  const { enabled = true } = options
  const callbackRef = useRef(callback)
  callbackRef.current = callback

  useEffect(() => {
    if (!enabled || delayMs == null || delayMs <= 0) return undefined

    let id = null

    function stop() {
      if (id != null) {
        clearInterval(id)
        id = null
      }
    }

    function start() {
      if (id != null || document.hidden) return
      id = setInterval(() => callbackRef.current(), delayMs)
    }

    function sync() {
      if (!enabled || document.hidden) stop()
      else start()
    }

    sync()
    document.addEventListener('visibilitychange', sync)
    return () => {
      stop()
      document.removeEventListener('visibilitychange', sync)
    }
  }, [delayMs, enabled])
}
