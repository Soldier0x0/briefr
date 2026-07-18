import { useCallback, useEffect, useRef, useState } from 'react'
import { Bell } from 'lucide-react'
import {
  dismissAllNotifications,
  dismissNotification,
  fetchNotifications,
  markNotificationsSeen,
} from '../utils/notificationsApi.js'
import { playNotificationChime } from '../utils/notificationChime.js'
import { fmtIso } from '../pages/admin/formatters.js'
import { NotificationListSkeleton } from '../pages/admin/shared/AdminSkeletons.jsx'
import './NotificationBell.css'

const UNDO_MS = 5000
const POLL_MS = 30_000

function useNotificationSoundEnabled() {
  const [enabled, setEnabled] = useState(true)
  useEffect(() => {
    function read() {
      try {
        const raw = localStorage.getItem('briefr_notification_sound')
        setEnabled(raw !== '0')
      } catch {
        setEnabled(true)
      }
    }
    read()
    window.addEventListener('briefr-preferences-loaded', read)
    return () => window.removeEventListener('briefr-preferences-loaded', read)
  }, [])
  return enabled
}

export default function NotificationBell({ scope = 'analyst', className = '' }) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [hiddenIds, setHiddenIds] = useState(() => new Set())
  const [undo, setUndo] = useState(null)
  const undoTimerRef = useRef(null)
  const prevUnreadRef = useRef(0)
  const rootRef = useRef(null)
  const soundEnabled = useNotificationSoundEnabled()

  const clearUndoTimer = useCallback(() => {
    if (undoTimerRef.current) {
      clearTimeout(undoTimerRef.current)
      undoTimerRef.current = null
    }
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchNotifications(scope)
      setItems(data.notifications || [])
      setUnreadCount(data.unread_count || 0)
    } catch {
      setItems([])
      setUnreadCount(0)
    } finally {
      setLoading(false)
    }
  }, [scope])

  useEffect(() => {
    load()
    const id = setInterval(load, POLL_MS)
    return () => clearInterval(id)
  }, [load])

  useEffect(() => {
    if (unreadCount > prevUnreadRef.current && soundEnabled) {
      playNotificationChime()
    }
    prevUnreadRef.current = unreadCount
  }, [unreadCount, soundEnabled])

  useEffect(() => () => clearUndoTimer(), [clearUndoTimer])

  useEffect(() => {
    if (!open) return undefined
    function onDown(e) {
      if (rootRef.current?.contains(e.target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  const visibleItems = items.filter(n => !hiddenIds.has(n.id))

  function scheduleDismiss(commitFn, restoreFn, label) {
    clearUndoTimer()
    setUndo({ label, restore: restoreFn })
    undoTimerRef.current = setTimeout(async () => {
      undoTimerRef.current = null
      setUndo(null)
      try {
        await commitFn()
      } catch {
        restoreFn()
      }
      await load()
    }, UNDO_MS)
  }

  function dismissOne(item) {
    setHiddenIds(prev => new Set(prev).add(item.id))
    scheduleDismiss(
      () => dismissNotification(item.id),
      () => setHiddenIds(prev => {
        const next = new Set(prev)
        next.delete(item.id)
        return next
      }),
      'Notification dismissed',
    )
  }

  function dismissAll() {
    const ids = visibleItems.map(n => n.id)
    if (!ids.length) return
    setHiddenIds(prev => new Set([...prev, ...ids]))
    scheduleDismiss(
      () => dismissAllNotifications(scope),
      () => setHiddenIds(prev => {
        const next = new Set(prev)
        ids.forEach(id => next.delete(id))
        return next
      }),
      `${ids.length} notification${ids.length === 1 ? '' : 's'} dismissed`,
    )
  }

  function handleUndo() {
    clearUndoTimer()
    if (undo?.restore) undo.restore()
    setUndo(null)
    setHiddenIds(new Set())
  }

  async function toggleOpen() {
    const next = !open
    setOpen(next)
    if (next) {
      try {
        const res = await markNotificationsSeen(scope)
        setUnreadCount(res.unread_count ?? 0)
      } catch {
        /* keep badge */
      }
      await load()
    }
  }

  function handleItemClick(item) {
    if (item.entity_type === 'cve' && item.entity_id) {
      const url = new URL(window.location.href)
      url.pathname = '/'
      url.searchParams.set('tab', 'feed')
      url.searchParams.set('cve', item.entity_id)
      window.location.assign(url.toString())
    } else if (item.entity_type === 'ioc' && item.entity_id) {
      const url = new URL(window.location.href)
      url.pathname = '/'
      url.searchParams.set('tab', 'ioc')
      url.searchParams.set('ioc', item.entity_id)
      window.location.assign(url.toString())
    } else if (item.entity_type === 'kev_backlog') {
      // Analyst shell uses tab=; Forge still owns view=/technique=/pack=.
      const url = new URL(window.location.href)
      url.pathname = '/'
      url.searchParams.set('tab', 'forge')
      url.searchParams.set('view', 'backlog')
      window.location.assign(url.toString())
    } else if (item.entity_type === 'webhook' && item.entity_id) {
      window.location.assign(`/admin?p=webhooks`)
    } else if (item.entity_type === 'api_key' && item.entity_id) {
      window.location.assign('/admin?p=apikeys')
    } else if (item.entity_type === 'job' && item.entity_id) {
      window.location.assign(`/admin?p=scheduler&job_id=${encodeURIComponent(item.entity_id)}`)
    }
  }

  return (
    <div ref={rootRef} className={`notification-bell ${className}`.trim()}>
      <button
        type="button"
        className="notification-bell-trigger"
        aria-expanded={open}
        aria-label="Notifications"
        onClick={toggleOpen}
      >
        <Bell size={16} aria-hidden />
        {unreadCount > 0 && (
          <span className="notification-bell-badge" aria-hidden>{unreadCount}</span>
        )}
      </button>
      {open && (
        <div className="notification-bell-panel" role="region" aria-label="Notifications">
          <div className="notification-bell-head">
            <strong className="notification-bell-title">Notifications</strong>
            <div className="notification-bell-actions">
              {visibleItems.length > 0 && (
                <button type="button" className="notification-bell-link" onClick={dismissAll}>
                  Mark all read
                </button>
              )}
              <button type="button" className="notification-bell-link" onClick={load} disabled={loading}>
                Refresh
              </button>
            </div>
          </div>
          {loading && !items.length && (
            <NotificationListSkeleton rows={3} />
          )}
          {!loading && !visibleItems.length && (
            <p className="notification-bell-empty mono">No notifications.</p>
          )}
          <ul className="notification-bell-list">
            {visibleItems.map(item => (
              <li key={item.id} className={`notification-bell-item notification-bell-item--${item.severity}`}>
                <div className="notification-bell-item-main">
                  <button
                    type="button"
                    className="notification-bell-item-title"
                    onClick={() => handleItemClick(item)}
                  >
                    {item.title}
                  </button>
                  {item.body && (
                    <p className="notification-bell-item-body">{item.body}</p>
                  )}
                  {item.created_at && (
                    <span className="notification-bell-item-time mono">{fmtIso(item.created_at)}</span>
                  )}
                </div>
                <button
                  type="button"
                  className="notification-bell-link"
                  onClick={() => dismissOne(item)}
                >
                  Mark read
                </button>
              </li>
            ))}
          </ul>
          {undo && (
            <div className="notification-bell-undo">
              <span>{undo.label}</span>
              <button type="button" className="notification-bell-link" onClick={handleUndo}>
                Undo
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
