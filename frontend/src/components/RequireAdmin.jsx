import { Navigate, useLocation, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

/** Analyst-accessible admin sub-pages (operator routes require admin role). */
const ANALYST_ADMIN_PAGES = new Set(['display', 'securityposture'])

export default function RequireAdmin({ children }) {
  const { status, user } = useAuth()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const page = searchParams.get('p') || 'overview'

  if (status === 'loading') {
    return (
      <div className="app-auth-loading" role="status" aria-label="Checking session">
        <span className="app-auth-loading-dot" />
      </div>
    )
  }

  if (status === 'anon') {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (user?.role !== 'admin' && !ANALYST_ADMIN_PAGES.has(page)) {
    return <Navigate to="/" replace state={{ adminDenied: true }} />
  }

  return children
}
