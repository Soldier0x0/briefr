import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ChevronDown, Home, LayoutDashboard, LogOut, Settings } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import './UserMenu.css'

export default function UserMenu({ className = '', onItemClick }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)

  const username = user?.username || 'account'
  const role = user?.role || ''
  const initial = username.charAt(0).toUpperCase()
  const onAdmin = location.pathname.startsWith('/admin')

  useEffect(() => {
    if (!open) return

    function onDown(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    function onKey(e) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  async function handleLogout() {
    setOpen(false)
    onItemClick?.()
    try {
      await logout()
    } finally {
      navigate('/login')
    }
  }

  function close() {
    setOpen(false)
    onItemClick?.()
  }

  return (
    <div className={`user-menu-wrap${className ? ` ${className}` : ''}`} ref={wrapRef}>
      <button
        type="button"
        className="user-menu-trigger"
        onClick={() => setOpen(v => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${username}`}
      >
        <span className="user-menu-avatar" aria-hidden="true">{initial}</span>
        <span className="user-menu-name mono">{username}</span>
        <ChevronDown size={14} className={`user-menu-chevron${open ? ' open' : ''}`} aria-hidden="true" />
      </button>

      {open && (
        <div className="user-menu-dropdown" role="menu" aria-label="Account menu">
          <div className="user-menu-header">
            <span className="user-menu-avatar user-menu-avatar--lg" aria-hidden="true">{initial}</span>
            <div className="user-menu-header-text">
              <span className="user-menu-header-name">{username}</span>
              {role && <span className="user-menu-header-role">{role}</span>}
            </div>
          </div>
          <div className="user-menu-group">
            {onAdmin ? (
              <Link to="/" className="user-menu-item" role="menuitem" onClick={close}>
                <Home size={14} aria-hidden="true" />
                <span>Back to BRIEFR</span>
              </Link>
            ) : (
              <Link to="/admin" className="user-menu-item" role="menuitem" onClick={close}>
                <LayoutDashboard size={14} aria-hidden="true" />
                <span>Admin panel</span>
              </Link>
            )}
            <Link to="/admin?p=display" className="user-menu-item" role="menuitem" onClick={close}>
              <Settings size={14} aria-hidden="true" />
              <span>Preferences</span>
            </Link>
          </div>
          <div className="user-menu-group">
            <button type="button" className="user-menu-item user-menu-item-danger" role="menuitem" onClick={handleLogout}>
              <LogOut size={14} aria-hidden="true" />
              <span>Log out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
