import { useEffect, useRef, useState } from 'react'
import { BACKEND_RESTART_EVENT } from '../../../utils/backendRestart.js'

const POLL_MS = 2000
const BACK_MS = 4000

export default function RestartBanner() {
  const [phase, setPhase] = useState('hidden') // hidden | restarting | online
  const pollRef = useRef(null)

  useEffect(() => {
    function onRestarting() {
      setPhase('restarting')
    }
    window.addEventListener(BACKEND_RESTART_EVENT, onRestarting)
    return () => window.removeEventListener(BACKEND_RESTART_EVENT, onRestarting)
  }, [])

  useEffect(() => {
    if (phase !== 'restarting') return undefined

    let cancelled = false

    async function pollHealth() {
      if (cancelled) return
      try {
        const res = await fetch('/api/health', { cache: 'no-store' })
        if (cancelled) return
        if (res.ok) {
          setPhase('online')
          return
        }
      } catch { /* backend still down */ }
      if (cancelled) return
      pollRef.current = setTimeout(pollHealth, POLL_MS)
    }

    pollRef.current = setTimeout(pollHealth, POLL_MS)
    return () => {
      cancelled = true
      if (pollRef.current) clearTimeout(pollRef.current)
    }
  }, [phase])

  useEffect(() => {
    if (phase !== 'online') return undefined
    const timer = setTimeout(() => setPhase('hidden'), BACK_MS)
    return () => clearTimeout(timer)
  }, [phase])

  if (phase === 'hidden') return null

  const message = phase === 'restarting'
    ? 'Backend is restarting — settings will apply when it is back online.'
    : 'Backend is back online.'

  return (
    <div className={`admin-restart-banner admin-restart-banner--${phase}`} role="status" aria-live="polite">
      {phase === 'restarting' && <span className="admin-spinner" aria-hidden="true" />}
      <span>{message}</span>
    </div>
  )
}
