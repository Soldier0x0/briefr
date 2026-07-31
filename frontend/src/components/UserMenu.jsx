import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Layers, LogOut, Settings, Home, LayoutDashboard, ChevronDown, Sparkles } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
  Switch,
} from './ui/index.js'
import { getDisplayPrefs, setDisplayPrefs } from '../utils/displayPrefs.js'
import './UserMenu.css'

export default function UserMenu({
  className = '',
  onItemClick,
  onMyStack,
  onClearSession,
  showClearSession = false,
}) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const username = user?.username || 'account'
  const role = user?.role || ''
  const initial = username.charAt(0).toUpperCase()
  const onAdmin = location.pathname.startsWith('/admin')
  const [showcaseUi, setShowcaseUi] = useState(() => getDisplayPrefs().uiVariant === 'pitch')

  useEffect(() => {
    function sync() {
      setShowcaseUi(getDisplayPrefs().uiVariant === 'pitch')
    }
    window.addEventListener('briefr-preferences-loaded', sync)
    window.addEventListener('briefr-display-prefs-changed', sync)
    return () => {
      window.removeEventListener('briefr-preferences-loaded', sync)
      window.removeEventListener('briefr-display-prefs-changed', sync)
    }
  }, [])

  async function toggleShowcaseUi(checked) {
    setShowcaseUi(checked)
    try {
      await setDisplayPrefs({ uiVariant: checked ? 'pitch' : 'default' })
    } catch {
      setShowcaseUi(getDisplayPrefs().uiVariant === 'pitch')
    }
  }

  async function handleLogout() {
    onItemClick?.()
    try {
      await logout()
    } finally {
      navigate('/login')
    }
  }

  function close() {
    onItemClick?.()
  }

  return (
    <div className={`user-menu-wrap${className ? ` ${className}` : ''}`}>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="user-menu-trigger"
            aria-label={`Account menu for ${username}`}
          >
            <span className="user-menu-avatar" aria-hidden="true">{initial}</span>
            <span className="user-menu-name mono">{username}</span>
            <ChevronDown size={14} className="user-menu-chevron" aria-hidden="true" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="user-menu-dropdown" align="end" sideOffset={6}>
          <DropdownMenuLabel className="user-menu-header">
            <span className="user-menu-avatar user-menu-avatar--lg" aria-hidden="true">{initial}</span>
            <div className="user-menu-header-text">
              <span className="user-menu-header-name">{username}</span>
              {role && <span className="user-menu-header-role">{role}</span>}
            </div>
          </DropdownMenuLabel>
          {onMyStack && (
            <DropdownMenuItem className="user-menu-item" onSelect={() => { close(); onMyStack() }}>
              <Layers size={14} aria-hidden="true" />
              <span>My Stack</span>
            </DropdownMenuItem>
          )}
          {onAdmin ? (
            <DropdownMenuItem asChild>
              <Link to="/" className="user-menu-item" onClick={close}>
                <Home size={14} aria-hidden="true" />
                <span>Back to BRIEFR</span>
              </Link>
            </DropdownMenuItem>
          ) : role === 'admin' ? (
            <DropdownMenuItem asChild>
              <Link to="/admin" className="user-menu-item" onClick={close}>
                <LayoutDashboard size={14} aria-hidden="true" />
                <span>Admin panel</span>
              </Link>
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuItem asChild>
            <Link to="/admin?p=display" className="user-menu-item" onClick={close}>
              <Settings size={14} aria-hidden="true" />
              <span>Preferences</span>
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem
            className="user-menu-item user-menu-item-toggle"
            onSelect={(event) => event.preventDefault()}
          >
            <Sparkles size={14} aria-hidden="true" />
            <span className="user-menu-toggle-label">Showcase card style</span>
            <Switch
              checked={showcaseUi}
              onCheckedChange={(checked) => { void toggleShowcaseUi(checked) }}
              aria-label="Toggle showcase card style"
            />
          </DropdownMenuItem>
          {showClearSession && onClearSession && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="user-menu-item" onSelect={() => { close(); onClearSession() }}>
                <span>Clear session</span>
              </DropdownMenuItem>
            </>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem className="user-menu-item user-menu-item-danger" onSelect={handleLogout}>
            <LogOut size={14} aria-hidden="true" />
            <span>Log out</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
