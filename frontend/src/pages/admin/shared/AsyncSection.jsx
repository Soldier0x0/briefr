import { Loader2, AlertCircle, Inbox } from 'lucide-react'

// Wraps a page's primary data load in a consistent loading / error / empty / success
// state, so failed API calls surface a retry button instead of hanging on "Loading…"
// forever (the old PageBackups/PageStorage/etc. pattern of catch { setX([]) }).
export default function AsyncSection({ data, error, loading, onRetry, emptyMessage = 'No entries', children }) {
  if (loading && data == null) {
    return (
      <div className="admin-empty">
        <Loader2 className="admin-empty-icon spin" size={20} strokeWidth={2} />
        <div>Loading…</div>
      </div>
    )
  }
  if (error) {
    return (
      <div className="admin-empty" style={{ color: 'var(--red)' }}>
        <AlertCircle className="admin-empty-icon" size={20} strokeWidth={2} />
        <div>Failed to load: {String(error.message || error)}</div>
        {onRetry && (
          <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
    )
  }
  if (data == null) {
    return (
      <div className="admin-empty">
        <Loader2 className="admin-empty-icon spin" size={20} strokeWidth={2} />
        <div>Loading…</div>
      </div>
    )
  }
  if (Array.isArray(data) && data.length === 0) {
    return (
      <div className="admin-empty">
        <Inbox className="admin-empty-icon" size={20} strokeWidth={2} />
        <div>{emptyMessage}</div>
      </div>
    )
  }
  return children(data)
}
