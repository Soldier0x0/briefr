// Wraps a page's primary data load in a consistent loading / error / empty / success
// state, so failed API calls surface a retry button instead of hanging on "Loading…"
// forever (the old PageBackups/PageStorage/etc. pattern of catch { setX([]) }).
export default function AsyncSection({ data, error, loading, onRetry, emptyMessage = 'No entries', children }) {
  if (loading && data == null) return <div className="admin-empty">Loading…</div>
  if (error) {
    return (
      <div className="admin-empty" style={{ color: 'var(--red)' }}>
        Failed to load: {String(error.message || error)}
        {onRetry && (
          <button className="admin-btn admin-btn-ghost" style={{ marginLeft: '0.75rem', fontSize: '0.75rem' }} onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
    )
  }
  if (data == null) return <div className="admin-empty">Loading…</div>
  if (Array.isArray(data) && data.length === 0) return <div className="admin-empty">{emptyMessage}</div>
  return children(data)
}
