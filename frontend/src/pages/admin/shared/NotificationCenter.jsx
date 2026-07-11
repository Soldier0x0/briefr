import { useEffect, useState } from 'react'
import { Bell } from 'lucide-react'
import { adminApi } from '../../../api.js'
import { fmtIso } from '../formatters.js'
import {
  ackAllNotifications,
  ackNotification,
  countUnackedActionable,
  isActionableNotification,
  loadAckedKeys,
  notificationEventKey,
} from './adminNotificationsAck.js'
import './NotificationCenter.css'

export default function NotificationCenter() {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [acked, setAcked] = useState(() => loadAckedKeys())

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

  const events = data?.events || []
  const alertCount = countUnackedActionable(events, acked)
  const hasUnread = events.some(evt => !acked.has(notificationEventKey(evt)))

  function markRead(evt) {
    setAcked(prev => ackNotification(prev, evt))
  }

  function markAllRead() {
    setAcked(prev => ackAllNotifications(prev, events))
  }

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
            <strong className="notification-center-title">Notifications</strong>
            <div className="notification-center-actions">
              {hasUnread && (
                <button
                  type="button"
                  className="notification-center-mark-all"
                  onClick={markAllRead}
                >
                  Mark all read
                </button>
              )}
              <button
                type="button"
                className="notification-center-refresh"
                onClick={load}
                disabled={loading}
              >
                Refresh
              </button>
            </div>
          </div>
          {loading && !data && <p className="mono notification-center-empty">Loading…</p>}
          {!loading && !events.length && (
            <p className="mono notification-center-empty">No recent operator events.</p>
          )}
          <ul className="notification-center-list">
            {events.map((evt, idx) => {
              const key = notificationEventKey(evt) || `${evt.type}-${idx}`
              const isRead = acked.has(notificationEventKey(evt))
              return (
                <li
                  key={key}
                  className={`notification-center-item${isRead ? ' notification-center-item--read' : ''}`}
                >
                  <span className="notification-center-type mono">{evt.type}</span>
                  <span className="notification-center-summary">
                    {evt.action || evt.job_id || evt.provider || 'event'}
                    {evt.summary ? ` — ${evt.summary}` : ''}
                  </span>
                  {evt.created_at && (
                    <span className="notification-center-time mono">{fmtIso(evt.created_at)}</span>
                  )}
                  {!isRead && (
                    <button
                      type="button"
                      className="notification-center-mark-read"
                      onClick={() => markRead(evt)}
                      aria-label={
                        isActionableNotification(evt)
                          ? 'Mark alert as read'
                          : 'Mark notification as read'
                      }
                    >
                      Mark read
                    </button>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
