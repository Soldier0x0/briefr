import { useEffect, useRef, useState } from 'react'
import { getLiveQueueSummary } from '../utils/apiQueuePresentation.js'

function queueIsThrottled(apiQueue) {
  if (!apiQueue) return false
  if (apiQueue.requests?.some(r => String(r.state).toLowerCase() === 'rate_limited')) {
    return true
  }
  return Object.values(apiQueue.sources ?? {}).some(s => s.paused_for_seconds > 0)
}

export function useApiQueueLive(apiQueue) {
  const receivedAtRef = useRef(Date.now())
  const queueRef = useRef(apiQueue)
  if (apiQueue !== queueRef.current) {
    queueRef.current = apiQueue
    receivedAtRef.current = Date.now()
  }

  const throttled = queueIsThrottled(apiQueue)
  const [nowMs, setNowMs] = useState(() => Date.now())

  useEffect(() => {
    if (!throttled) return undefined
    const id = setInterval(() => setNowMs(Date.now()), 1000)
    return () => clearInterval(id)
  }, [throttled, apiQueue])

  const summary = getLiveQueueSummary(apiQueue, nowMs, receivedAtRef.current)
  return { summary, snapshotAgeMs: nowMs - receivedAtRef.current }
}
