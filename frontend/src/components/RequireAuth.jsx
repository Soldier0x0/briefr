import { Navigate, useLocation } from 'react-router-dom'
import LogoMark from './LogoMark.jsx'
import { useAuth } from '../context/AuthContext.jsx'

export default function RequireAuth({ children }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <div className="app-auth-loading" role="status" aria-label="Checking session">
        <LogoMark size="md" className="app-auth-loading-mark" />
      </div>
    )
  }

  if (status === 'anon') {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
