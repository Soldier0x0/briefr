import { useState, useRef, useEffect } from 'react'
import { Clock } from 'lucide-react'
import './ApiQueueIndicator.css'

function formatSourceLabel(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export default function ApiQueueIndicator({ apiQueue, className = '' }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  const queued = apiQueue?.total_queued ?? 0
  const active = apiQueue?.total_active ?? 0
  const sources = apiQueue?.sources ?? {}
  const pending = Boolean(apiQueue?.has_pending || queued > 0 || active > 0)

  useEffect(() => {
    if (!open) return undefined
    function onDown(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  if (!pending) return null

  const count = queued + active
  const sourceEntries = Object.entries(sources)

  return (
    <div className={`api-queue-indicator ${className}`.trim()} ref={ref}>
      <button
        type="button"
        className="api-queue-btn"
        onClick={() => setOpen(v => !v)}
        aria-label={`${count} API request${count === 1 ? '' : 's'} queued or in progress`}
        title="Outbound API requests waiting on rate limits"
      >
        <Clock size={14} strokeWidth={2} aria-hidden="true" />
        <span className="api-queue-count mono">{count}</span>
      </button>
      {open && (
        <div className="api-queue-dropdown" role="status">
          <div className="api-queue-dropdown-title">API queue</div>
          <p className="api-queue-dropdown-sub">
            Requests wait for provider rate limits — nothing is dropped.
          </p>
          <div className="api-queue-summary mono">
            <span>{queued} queued</span>
            <span aria-hidden="true"> · </span>
            <span>{active} active</span>
          </div>
          {sourceEntries.length > 0 && (
            <ul className="api-queue-sources">
              {sourceEntries.map(([key, info]) => (
                <li key={key}>
                  <span className="api-queue-source-name">{formatSourceLabel(key)}</span>
                  <span className="api-queue-source-meta mono">
                    {[
                      info.queued > 0 && `${info.queued} waiting`,
                      info.active > 0 && `${info.active} active`,
                      info.paused_for_seconds > 0 && `${info.paused_for_seconds}s pause`,
                    ].filter(Boolean).join(' · ')}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
