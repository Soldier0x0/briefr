import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bell,
  Info,
  MoreHorizontal,
  OctagonAlert,
  TriangleAlert,
} from 'lucide-react'
import {
  dismissNotification,
  fetchNotifications,
  readAllNotifications,
  readNotification,
  restoreNotification,
} from '../utils/notificationsApi.js'
import {
  groupNotificationRows,
  notificationDestination,
  notificationTriggerLabel,
} from '../utils/notificationInbox.js'
import { playNotificationChime } from '../utils/notificationChime.js'
import { formatTimeAgo } from '../utils/timeAgo.js'
import { fmtIso } from '../pages/admin/formatters.js'
import { NotificationListSkeleton } from '../pages/admin/shared/AdminSkeletons.jsx'
import {
  AsyncState,
  Badge,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  Popover,
  PopoverContent,
  PopoverTrigger,
  Tabs,
  TabsList,
  TabsTrigger,
} from './ui/index.js'
import './NotificationBell.css'

const UNDO_MS = 5000
const POLL_MS = 30_000

const CATEGORY_LABELS = {
  watchlist: 'Watchlist',
  ioc_watchlist: 'IOC watchlist',
  job_error: 'Job error',
  api_key_unhealthy: 'API key',
  webhook_failure: 'Webhook',
}

const SEVERITY = {
  critical: {
    Icon: OctagonAlert,
    badge: 'danger',
    label: 'Critical',
    explain: 'Critical severity notification.',
  },
  high: {
    Icon: TriangleAlert,
    badge: 'warn',
    label: 'High',
    explain: 'High severity notification.',
  },
  medium: {
    Icon: Info,
    badge: 'info',
    label: 'Medium',
    explain: 'Medium severity notification.',
  },
  low: {
    Icon: Info,
    badge: 'neutral',
    label: 'Low',
    explain: 'Low severity notification.',
  },
}

function severityDetails(value) {
  return SEVERITY[value] || {
    Icon: Info,
    badge: 'neutral',
    label: 'Info',
    explain: 'Informational notification.',
  }
}

function groupIsUnread(group) {
  return [group.latest, ...group.extras].some(item => !item.read_at)
}

function NotificationRow({
  group,
  active,
  view,
  onOpen,
  onAction,
  rowRef,
}) {
  const item = group.latest
  const destination = notificationDestination(item)
  const unread = groupIsUnread(group)
  const severity = severityDetails(item.severity)
  const SeverityIcon = severity.Icon
  const actionLabel = view === 'done' ? 'Restore' : 'Done'
  const category = CATEGORY_LABELS[item.category] || item.category || 'Notification'

  function activate(event) {
    if (!destination) return
    event.preventDefault()
    event.stopPropagation()
    onOpen(item, destination)
  }

  return (
    <li
      className={[
        'notification-inbox-row',
        `notification-inbox-row--${SEVERITY[item.severity] ? item.severity : 'info'}`,
        unread ? 'notification-inbox-row--unread' : '',
        active ? 'notification-inbox-row--active' : '',
      ].filter(Boolean).join(' ')}
    >
      <div
        ref={rowRef}
        className={[
          'notification-inbox-row-hit',
          destination ? 'notification-inbox-row-hit--actionable' : '',
        ].filter(Boolean).join(' ')}
        role={destination ? 'button' : undefined}
        tabIndex={destination ? 0 : undefined}
        onClick={destination ? activate : undefined}
        onKeyDown={destination ? (event) => {
          if (event.key === 'Enter' || event.key === ' ') activate(event)
        } : undefined}
      >
        <span className="notification-inbox-unread-slot" aria-hidden="true">
          {unread && <span className="notification-inbox-unread-dot" />}
        </span>
        <span
          className="notification-inbox-severity-icon"
          data-severity={SEVERITY[item.severity] ? item.severity : 'info'}
          aria-hidden="true"
        >
          <SeverityIcon size={16} strokeWidth={2} />
        </span>
        <span className="notification-inbox-row-main">
          <span className="notification-inbox-row-title">{item.title}</span>
          {item.body && (
            <span className="notification-inbox-row-body">{item.body}</span>
          )}
          <span className="notification-inbox-row-meta mono">
            <Badge variant={severity.badge} explain={severity.explain}>
              {severity.label}
            </Badge>
            <span>{category}</span>
            {item.created_at && (
              <time dateTime={item.created_at} title={fmtIso(item.created_at)}>
                {formatTimeAgo(item.created_at)}
              </time>
            )}
            {group.extras.length > 0 && <span>+{group.extras.length} more</span>}
            {destination && <span>{destination.label}</span>}
          </span>
        </span>
        <button
          type="button"
          className="notification-inbox-row-action"
          aria-label={`${actionLabel}: ${item.title}`}
          onClick={(event) => {
            event.preventDefault()
            event.stopPropagation()
            onAction(item)
          }}
        >
          {actionLabel}
        </button>
      </div>
    </li>
  )
}

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
  const navigate = useNavigate()
  const panelTitleId = useId()
  const [open, setOpen] = useState(false)
  const [view, setView] = useState('inbox')
  const [items, setItems] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [undo, setUndo] = useState(null)
  const [activeIndex, setActiveIndex] = useState(0)
  const [chip, setChip] = useState('all')
  const [liveMessage, setLiveMessage] = useState('')
  const undoTimerRef = useRef(null)
  const prevUnreadRef = useRef(0)
  const requestRef = useRef(0)
  const rowRefs = useRef([])
  const soundEnabled = useNotificationSoundEnabled()

  const clearUndoTimer = useCallback(() => {
    if (undoTimerRef.current) {
      clearTimeout(undoTimerRef.current)
      undoTimerRef.current = null
    }
  }, [])

  const load = useCallback(async () => {
    const requestId = ++requestRef.current
    setLoading(true)
    try {
      const data = await fetchNotifications(scope, { view, limit: 50 })
      if (requestId !== requestRef.current) return
      setItems(data.notifications || [])
      setUnreadCount(data.unread_count || 0)
      setError(null)
    } catch (loadError) {
      if (requestId !== requestRef.current) return
      setError(loadError instanceof Error ? loadError : new Error('Notifications could not be loaded.'))
    } finally {
      if (requestId === requestRef.current) setLoading(false)
    }
  }, [scope, view])

  useEffect(() => {
    void load()
    const intervalId = setInterval(() => void load(), POLL_MS)
    function onVisibilityChange() {
      if (document.visibilityState === 'visible') void load()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      clearInterval(intervalId)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [load])

  useEffect(() => {
    if (open) void load()
  }, [open, load])

  useEffect(() => {
    if (unreadCount > prevUnreadRef.current && !open) {
      const added = unreadCount - prevUnreadRef.current
      setLiveMessage(`${added} new notification${added === 1 ? '' : 's'}. ${unreadCount} unread.`)
      if (soundEnabled) playNotificationChime()
    }
    prevUnreadRef.current = unreadCount
  }, [open, soundEnabled, unreadCount])

  useEffect(() => () => clearUndoTimer(), [clearUndoTimer])

  useEffect(() => {
    setChip('all')
  }, [scope])

  const showChips = scope === 'all' || new Set(items.map(item => item.scope).filter(Boolean)).size > 1
  const filteredItems = useMemo(() => items.filter((item) => {
    if (chip === 'intel') return item.scope === 'analyst'
    if (chip === 'ops') return item.scope === 'operator'
    return true
  }), [chip, items])
  const rows = useMemo(() => groupNotificationRows(filteredItems), [filteredItems])

  useEffect(() => {
    setActiveIndex(index => Math.min(index, Math.max(0, rows.length - 1)))
  }, [rows.length])

  useEffect(() => {
    if (!open) return
    rowRefs.current[activeIndex]?.scrollIntoView?.({ block: 'nearest' })
  }, [activeIndex, open])

  function beginUndo(ids, label) {
    clearUndoTimer()
    setUndo({ ids, label })
    undoTimerRef.current = setTimeout(() => {
      undoTimerRef.current = null
      setUndo(null)
    }, UNDO_MS)
  }

  async function handleOpen(item, destination) {
    navigate({ pathname: destination.pathname, search: destination.search })
    setOpen(false)
    if (item.read_at) return
    try {
      const result = await readNotification(item.id)
      setItems(current => current.map(row => (
        row.id === item.id ? { ...row, read_at: result.read_at || new Date().toISOString() } : row
      )))
      setUnreadCount(current => Math.max(0, result.unread_count ?? current - 1))
    } catch (readError) {
      setError(readError instanceof Error ? readError : new Error('Notification could not be marked as read.'))
    }
  }

  async function handleMarkAllRead() {
    try {
      const result = await readAllNotifications(scope)
      const readAt = new Date().toISOString()
      setItems(current => current.map(item => ({ ...item, read_at: item.read_at || readAt })))
      setUnreadCount(result.unread_count ?? 0)
      setError(null)
    } catch (readError) {
      setError(readError instanceof Error ? readError : new Error('Notifications could not be marked as read.'))
    }
  }

  async function handleDone(item) {
    try {
      const result = await dismissNotification(item.id)
      setItems(current => current.filter(row => row.id !== item.id))
      if (!item.read_at) {
        setUnreadCount(current => Math.max(0, result.unread_count ?? current - 1))
      }
      beginUndo([item.id], 'Moved to Done')
      setError(null)
    } catch (dismissError) {
      setError(dismissError instanceof Error ? dismissError : new Error('Notification could not be moved to Done.'))
    }
  }

  async function handleMoveAllDone() {
    const ids = filteredItems.map(item => item.id)
    if (!ids.length) return
    const results = await Promise.allSettled(ids.map(id => dismissNotification(id)))
    const dismissedIds = ids.filter((_, index) => results[index].status === 'fulfilled')
    const dismissedIdSet = new Set(dismissedIds)
    const dismissedUnread = filteredItems.filter(item => (
      dismissedIdSet.has(item.id) && !item.read_at
    )).length

    if (dismissedIds.length) {
      setItems(current => current.filter(item => !dismissedIdSet.has(item.id)))
      setUnreadCount(current => Math.max(0, current - dismissedUnread))
      beginUndo(
        dismissedIds,
        `${dismissedIds.length} notification${dismissedIds.length === 1 ? '' : 's'} moved to Done`,
      )
    }

    if (dismissedIds.length === ids.length) {
      setError(null)
    } else {
      setError(new Error(
        dismissedIds.length
          ? 'Some notifications could not be moved to Done.'
          : 'Notifications could not be moved to Done.',
      ))
    }
  }

  async function handleRestore(item) {
    try {
      await restoreNotification(item.id)
      setItems(current => current.filter(row => row.id !== item.id))
      setError(null)
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError : new Error('Notification could not be restored.'))
    }
  }

  async function handleUndo() {
    const ids = undo?.ids || []
    if (!ids.length) return
    clearUndoTimer()
    setUndo(null)
    try {
      await Promise.all(ids.map(id => restoreNotification(id)))
      await load()
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError : new Error('Notification could not be restored.'))
    }
  }

  function handleViewChange(nextView) {
    setLoading(true)
    setView(nextView)
    setItems([])
    setError(null)
    setChip('all')
    setActiveIndex(0)
  }

  function handleContentKeyDown(event) {
    const target = event.target
    if (target instanceof Element) {
      const notificationRow = target.closest('.notification-inbox-row-hit')
      const nestedControl = target.closest('button, a, [role="tab"], input, select, textarea')
      if ((nestedControl && nestedControl !== notificationRow) || target.isContentEditable) return
    }
    if (event.altKey || event.ctrlKey || event.metaKey || !rows.length) return

    if (event.key.toLowerCase() === 'j') {
      event.preventDefault()
      setActiveIndex(index => (index + 1) % rows.length)
      return
    }
    if (event.key.toLowerCase() === 'k') {
      event.preventDefault()
      setActiveIndex(index => (index - 1 + rows.length) % rows.length)
      return
    }

    const item = rows[activeIndex]?.latest
    if (!item) return
    if (event.key === 'Enter') {
      const destination = notificationDestination(item)
      if (destination) {
        event.preventDefault()
        void handleOpen(item, destination)
      }
    } else if (event.key.toLowerCase() === 'e') {
      event.preventDefault()
      if (view === 'done') void handleRestore(item)
      else void handleDone(item)
    }
  }

  const panelTitle = view === 'done' ? 'Done' : 'Inbox'

  return (
    <div className={`notification-bell ${className}`.trim()}>
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {liveMessage}
      </span>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            className="notification-bell-trigger"
            aria-label={notificationTriggerLabel(unreadCount)}
          >
            <Bell size={16} aria-hidden="true" />
            {unreadCount > 0 && (
              <span className="notification-bell-badge">{unreadCount}</span>
            )}
          </button>
        </PopoverTrigger>
        <PopoverContent
          className="notification-inbox-panel"
          collisionPadding={12}
          aria-labelledby={panelTitleId}
          onKeyDown={handleContentKeyDown}
        >
          <div className="notification-inbox-head">
            <h2 id={panelTitleId} className="notification-inbox-title">{panelTitle}</h2>
            <div className="notification-inbox-head-actions">
              {view === 'inbox' && unreadCount > 0 && (
                <button
                  type="button"
                  className="notification-inbox-text-action"
                  onClick={() => void handleMarkAllRead()}
                >
                  Mark all as read
                </button>
              )}
              {view === 'inbox' && filteredItems.length > 0 && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      className="notification-inbox-icon-action"
                      aria-label="Notification actions"
                    >
                      <MoreHorizontal size={16} aria-hidden="true" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onSelect={() => void handleMoveAllDone()}>
                      Move all to Done
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          </div>

          <Tabs value={view} onValueChange={handleViewChange}>
            <TabsList className="notification-inbox-tabs" aria-label="Notification views">
              <TabsTrigger value="inbox">Inbox</TabsTrigger>
              <TabsTrigger value="done">Done</TabsTrigger>
            </TabsList>
          </Tabs>

          {showChips && (
            <div className="notification-inbox-chips" aria-label="Filter notifications">
              {[
                ['all', 'All'],
                ['intel', 'Intel'],
                ['ops', 'Ops'],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={`notification-inbox-chip${chip === value ? ' notification-inbox-chip--active' : ''}`}
                  aria-pressed={chip === value}
                  onClick={() => {
                    setChip(value)
                    setActiveIndex(0)
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          )}

          <div className="notification-inbox-scroll">
            <AsyncState
              loading={loading && items.length === 0}
              refreshing={loading && items.length > 0}
              error={error}
              onRetry={() => void load()}
              empty={!loading && !error && rows.length === 0}
              emptyTitle={view === 'done' ? 'Nothing in Done yet.' : 'Inbox is clear.'}
              skeleton={<NotificationListSkeleton rows={3} />}
              data={rows}
              className="notification-inbox-state"
            >
              <ul className="notification-inbox-list">
                {rows.map((group, index) => (
                  <NotificationRow
                    key={group.latest.id ?? group.key}
                    group={group}
                    active={index === activeIndex}
                    view={view}
                    onOpen={(item, destination) => void handleOpen(item, destination)}
                    onAction={(item) => (
                      view === 'done' ? void handleRestore(item) : void handleDone(item)
                    )}
                    rowRef={(node) => {
                      rowRefs.current[index] = node
                    }}
                  />
                ))}
              </ul>
            </AsyncState>
          </div>

          {undo && (
            <div className="notification-inbox-undo" role="status">
              <span>{undo.label}</span>
              <button
                type="button"
                className="notification-inbox-text-action"
                onClick={() => void handleUndo()}
              >
                Undo
              </button>
            </div>
          )}
        </PopoverContent>
      </Popover>
    </div>
  )
}
