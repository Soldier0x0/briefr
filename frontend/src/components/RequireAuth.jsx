import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function RequireAuth({ children }) {
  const { status } = useAuth()
  const location = useLocation()

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

  return children
}
