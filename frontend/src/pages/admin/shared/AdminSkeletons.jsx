import { Skeleton } from '../../../components/ui/index.js'

/** Skeleton rows for `<tbody>` — preserves table layout while loading (E7-2). */
export function AdminTableBodySkeletonRows({ rows = 5, cols = 5 }) {
  return Array.from({ length: rows }).map((_, rowIndex) => (
    <tr key={rowIndex} className="admin-skeleton-tr" aria-hidden="true">
      {Array.from({ length: cols }).map((__, colIndex) => (
        <td key={colIndex}>
          <Skeleton
            variant="text"
            className="admin-skeleton-cell"
            style={{
              width: colIndex === 0 ? '72%' : colIndex === cols - 1 ? '48%' : '88%',
            }}
          />
        </td>
      ))}
    </tr>
  ))
}

export function AdminStatRowSkeleton({ count = 4 }) {
  return (
    <div className="stat-card-row admin-skeleton-stat-row" role="status" aria-label="Loading">
      {Array.from({ length: count }).map((_, index) => (
        <Skeleton key={index} variant="block" className="admin-skeleton-stat-card" />
      ))}
    </div>
  )
}

export function AdminChartSkeleton({ height = 180 }) {
  return (
    <Skeleton
      variant="block"
      className="admin-skeleton-chart"
      style={{ height }}
      aria-label="Loading chart"
    />
  )
}

export function AdminFormSkeleton({ fields = 6 }) {
  return (
    <div className="admin-skeleton-form" role="status" aria-label="Loading">
      {Array.from({ length: fields }).map((_, index) => (
        <div key={index} className="admin-skeleton-form-row">
          <Skeleton variant="text" style={{ width: '28%' }} />
          <Skeleton variant="block" className="admin-skeleton-form-field" />
        </div>
      ))}
    </div>
  )
}

/**
 * Full-section placeholder for AsyncSection initial loads.
 * @param {'default'|'table'|'chart'|'form'} variant
 */
export function AdminPageSkeleton({ variant = 'default' }) {
  if (variant === 'table') {
    return (
      <div className="admin-card admin-skeleton-page" role="status" aria-label="Loading">
        <table className="admin-table admin-skeleton-table">
          <tbody>
            <AdminTableBodySkeletonRows rows={6} cols={5} />
          </tbody>
        </table>
      </div>
    )
  }

  if (variant === 'chart') {
    return (
      <div className="admin-skeleton-page" role="status" aria-label="Loading">
        <AdminStatRowSkeleton count={3} />
        <div className="admin-card">
          <AdminChartSkeleton height={200} />
        </div>
        <div className="admin-card">
          <AdminChartSkeleton height={200} />
        </div>
      </div>
    )
  }

  if (variant === 'form') {
    return (
      <div className="admin-skeleton-page" role="status" aria-label="Loading">
        <Skeleton variant="text" style={{ width: '220px', height: '1.25rem', marginBottom: '0.75rem' }} />
        <Skeleton variant="text" style={{ width: 'min(60ch, 90%)', marginBottom: '1.25rem' }} />
        <AdminFormSkeleton fields={5} />
      </div>
    )
  }

  return (
    <div className="admin-skeleton-page" role="status" aria-label="Loading">
      <AdminStatRowSkeleton count={4} />
      <div className="admin-card">
        <Skeleton variant="block" className="admin-skeleton-panel" />
      </div>
    </div>
  )
}

export function NotificationListSkeleton({ rows = 3 }) {
  return (
    <ul className="notification-bell-list notification-bell-list--skeleton" aria-busy="true" aria-label="Loading notifications">
      {Array.from({ length: rows }).map((_, index) => (
        <li key={index} className="notification-bell-skeleton-item">
          <Skeleton variant="text" style={{ width: '58%' }} />
          <Skeleton variant="text" style={{ width: '92%', marginTop: '6px' }} />
        </li>
      ))}
    </ul>
  )
}
