import { useState, useRef, useEffect, useId } from 'react'
import { Clock } from 'lucide-react'
import {
  handleApiQueueDropdownKeyDown,
  summarizeQueue,
} from '../utils/apiQueuePresentation.js'
import './ApiQueueIndicator.css'

export default function ApiQueueIndicator({ apiQueue, className = '', defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  const ref = useRef(null)
  const panelId = useId()

  const summary = summarizeQueue(apiQueue)
  const { queued, active, count, tone, ariaLabel, rows } = summary
  const pending = Boolean(apiQueue?.has_pending || queued > 0 || active > 0)

  useEffect(() => {
    if (!open) return undefined
    function onDown(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    function onKey(e) {
      handleApiQueueDropdownKeyDown(e, setOpen)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!pending) return null

  return (
    <div className={`api-queue-indicator ${className}`.trim()} ref={ref}>
      <button
        type="button"
        className={`api-queue-btn api-queue-btn--${tone}`}
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={ariaLabel}
        title="Outbound API request queue"
      >
        <Clock size={14} strokeWidth={2} aria-hidden="true" />
        <span className="api-queue-count mono">{count}</span>
      </button>
      {open && (
        <div className="api-queue-dropdown" id={panelId} role="region" aria-label="API queue details">
          <div className="api-queue-dropdown-title">API queue</div>
          <p className="api-queue-dropdown-sub">
            Requests wait for provider limits — nothing is dropped.
          </p>
          <div className="api-queue-summary mono" aria-live="polite">
            <span className="api-queue-summary-stat">{queued} queued</span>
            <span className="api-queue-summary-stat">{active} active</span>
          </div>
          {rows.length > 0 && (
            <ul className="api-queue-requests">
              {rows.map(row => (
                <li
                  key={row.key}
                  className={`api-queue-request api-queue-request--${row.state}`}
                >
                  <div className="api-queue-request-head">
                    <span className="api-queue-request-dot" aria-hidden="true">●</span>
                    <span className="api-queue-request-source">{row.source}</span>
                    <span className={`api-queue-request-state api-queue-request-state--${row.state}`}>
                      {row.stateLabel}
                    </span>
                  </div>
                  {row.displayLabel && (
                    <div className="api-queue-request-label">{row.displayLabel}</div>
                  )}
                  {row.contextId && (
                    <div className="api-queue-request-context mono">{row.contextId}</div>
                  )}
                  {row.detail && (
                    <div className="api-queue-request-detail">{row.detail}</div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
