import { AlertCircle, Inbox } from 'lucide-react'
import { AdminPageSkeleton } from './AdminSkeletons.jsx'

// Wraps a page's primary data load in a consistent loading / error / empty / success
// state, so failed API calls surface a retry button instead of hanging on spinners
// forever (the old PageBackups/PageStorage/etc. pattern of catch { setX([]) }).
export default function AsyncSection({
  data,
  error,
  onRetry,
  emptyMessage = 'No entries',
  skeletonVariant = 'default',
  children,
}) {
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
    return <AdminPageSkeleton variant={skeletonVariant} />
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
