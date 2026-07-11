import { useEffect, useState } from 'react'
import { Bell } from 'lucide-react'
import { adminApi } from '../../../api.js'
import { fmtIso } from '../formatters.js'
import './NotificationCenter.css'

export default function NotificationCenter() {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const res = await adminApi.get('/notifications?limit=30')
      if (res.ok) setData(await res.json())
    } catch {
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 60_000)
    return () => clearInterval(id)
  }, [])

  const alertCount =
    (data?.counts?.api_key_alerts || 0) + (data?.counts?.job_errors || 0)

  return (
    <div className="notification-center">
      <button
        type="button"
        className="notification-center-trigger"
        aria-expanded={open}
        aria-label="Operator notifications"
        onClick={() => setOpen(v => !v)}
      >
        <Bell size={16} aria-hidden />
        {alertCount > 0 && (
          <span className="notification-center-badge">{alertCount}</span>
        )}
      </button>
      {open && (
        <div className="notification-center-panel" role="region" aria-label="Notifications">
          <div className="notification-center-head">
            <strong>Notifications</strong>
            <button type="button" className="notification-center-refresh" onClick={load} disabled={loading}>
              Refresh
            </button>
          </div>
          {loading && !data && <p className="mono notification-center-empty">Loading…</p>}
          {!loading && (!data?.events?.length) && (
            <p className="mono notification-center-empty">No recent operator events.</p>
          )}
          <ul className="notification-center-list">
            {(data?.events || []).map((evt, idx) => (
              <li key={`${evt.type}-${evt.id || evt.job_id || evt.provider || idx}`}>
                <span className="notification-center-type mono">{evt.type}</span>
                <span className="notification-center-summary">
                  {evt.action || evt.job_id || evt.provider || 'event'}
                  {evt.summary ? ` — ${evt.summary}` : ''}
                </span>
                {evt.created_at && (
                  <span className="notification-center-time mono">{fmtIso(evt.created_at)}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
