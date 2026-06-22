import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { useAssetProfileOptional } from '../context/AssetProfileContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import ShortcutsPanel from './ShortcutsPanel.jsx'
import {
  COMMON_TIMEZONES,
  formatTime,
  getTzAbbr,
  setTimezone as persistTimezone,
} from '../utils/timezone.js'
import './Header.css'

export default function Header({ activeTab, onTabChange, onAboutOpen, onLogoClick, onTimezoneChange, showShortcuts }) {
  const assetCtx = useAssetProfileOptional()
  const { status: authStatus, logout } = useAuth()
  const navigate = useNavigate()
  const [now, setNow]               = useState(new Date())
  const [tz, setTz]                 = useState(() => {
    try { return localStorage.getItem('briefr_timezone') || 'UTC' } catch { return 'UTC' }
  })
  const [popoverOpen, setPopoverOpen]   = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [search, setSearch]             = useState('')
  const popoverRef                      = useRef(null)
  const mobileMenuRef                   = useRef(null)

  // Tick every second
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  // Close popovers on outside click
  useEffect(() => {
    function onDown(e) {
      if (popoverOpen && popoverRef.current && !popoverRef.current.contains(e.target)) {
        setPopoverOpen(false)
        setSearch('')
      }
      if (mobileMenuOpen && mobileMenuRef.current && !mobileMenuRef.current.contains(e.target)) {
        setMobileMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [popoverOpen, mobileMenuOpen])

  async function handleLogout() {
    try { await logout() } finally { navigate('/login') }
  }

  function selectTz(newTz) {
    setTz(newTz)
    persistTimezone(newTz)
    if (onTimezoneChange) onTimezoneChange(newTz)
    setPopoverOpen(false)
    setSearch('')
  }

  // Formatted times
  const utcTime   = formatTime(now, 'UTC')
  const localTime = tz !== 'UTC' ? formatTime(now, tz) : null
  const tzAbbr    = tz !== 'UTC' ? getTzAbbr(tz, now) : null

  // Filtered timezone list
  const q = search.toLowerCase().trim()
  const filtered = q
    ? COMMON_TIMEZONES.filter(t =>
        t.tz.toLowerCase().includes(q) ||
        t.search.includes(q) ||
        getTzAbbr(t.tz, now).toLowerCase().includes(q)
      )
    : COMMON_TIMEZONES

  const TABS = [
    { id: 'brief', label: 'BRIEF', aria: 'Switch to morning brief' },
    { id: 'feed', label: 'FEED', aria: 'Switch to full CVE feed' },
    { id: 'ioc', label: 'IOC LOOKUP', aria: 'Switch to IOC lookup' },
    { id: 'atlas', label: 'INCIDENTS & NEWS', aria: 'Switch to incidents and news' },
    { id: 'forge', label: 'FORGE', aria: 'Switch to Forge detection engineering' },
  ]

  return (
    <>
    <header className="header" role="banner">
      <div className="header-inner">
        {/* Left: logo */}
        <div className="header-left">
          <button
            className="header-logo-btn"
            onClick={onLogoClick || (() => onTabChange?.('brief'))}
            aria-label="Go to morning brief"
          >
            BRIEFR
          </button>
          <span className="header-divider" aria-hidden="true">//</span>
          <span className="header-tagline">CVE intelligence</span>
        </div>

        {/* Center: tabs */}
        {activeTab !== null && (
          <nav className="header-nav" aria-label="Main navigation">
            <button
              className={`header-tab${activeTab === 'brief' ? ' active' : ''}`}
              onClick={() => onTabChange('brief')}
              aria-label="Switch to morning brief"
              aria-current={activeTab === 'brief' ? 'page' : undefined}
            >
              BRIEF
            </button>
            <button
              className={`header-tab${activeTab === 'feed' ? ' active' : ''}`}
              onClick={() => onTabChange('feed')}
              aria-label="Switch to full CVE feed"
              aria-current={activeTab === 'feed' ? 'page' : undefined}
            >
              FEED
            </button>
            <button
              className={`header-tab${activeTab === 'ioc' ? ' active' : ''}`}
              onClick={() => onTabChange('ioc')}
              aria-label="Switch to IOC lookup"
              aria-current={activeTab === 'ioc' ? 'page' : undefined}
            >
              IOC LOOKUP
            </button>
            <button
              className={`header-tab${activeTab === 'atlas' ? ' active' : ''}`}
              onClick={() => onTabChange('atlas')}
              aria-label="Switch to incidents and news"
              aria-current={activeTab === 'atlas' ? 'page' : undefined}
            >
              INCIDENTS &amp; NEWS
            </button>
            <button
              className={`header-tab${activeTab === 'forge' ? ' active' : ''}`}
              onClick={() => onTabChange('forge')}
              aria-label="Switch to Forge detection engineering"
              aria-current={activeTab === 'forge' ? 'page' : undefined}
            >
              FORGE
            </button>
          </nav>
        )}

        {/* Right: legal, live dot, clock */}
        <div className="header-right">
          {showShortcuts && <ShortcutsPanel placement="header" />}

          {assetCtx?.isLoaded && (
            <button
              type="button"
              className="header-clear-session mono"
              onClick={assetCtx.clearProfile}
            >
              Clear Session
            </button>
          )}

          {assetCtx && (
            <button
              type="button"
              className="header-profile-btn mono"
              onClick={assetCtx.openProfileFlow}
              aria-label="Open asset profile setup"
            >
              PROFILE
            </button>
          )}

          {/* Legal links — Feed has no page footer (infinite scroll), so they
              stay reachable here only on that tab; every other tab shows
              them in the footer instead. */}
          {activeTab === 'feed' && (
            <nav className="header-legal header-legal-desktop" aria-label="Legal links">
              <button className="header-legal-link" onClick={onAboutOpen} aria-label="About BRIEFR">
                About
              </button>
              <span className="header-legal-sep" aria-hidden="true">&middot;</span>
              <Link to="/privacy" className="header-legal-link">Privacy Policy</Link>
              <span className="header-legal-sep" aria-hidden="true">&middot;</span>
              <Link to="/terms" className="header-legal-link">Terms of Use</Link>
            </nav>
          )}

          {/* Admin link — only visible to a logged-in operator */}
          {authStatus === 'authed' && (
            <>
              <span className="header-legal-sep" style={{ margin: '0 0.25rem' }} aria-hidden="true" />
              <Link to="/admin" className="header-admin-link" aria-label="Open admin dashboard">
                Admin
              </Link>
              <button
                type="button"
                className="header-clear-session mono"
                onClick={handleLogout}
                aria-label="Log out"
                title="Log out"
              >
                <LogOut size={13} style={{ marginRight: '0.25rem', verticalAlign: '-2px' }} />
                Log out
              </button>
            </>
          )}

          {/* Mobile "···" menu */}
          <div className="mobile-menu-wrap header-legal-mobile" ref={mobileMenuRef}>
            <button
              className="mobile-menu-btn"
              onClick={() => setMobileMenuOpen(v => !v)}
              aria-label="Open navigation menu"
              aria-expanded={mobileMenuOpen}
            >
              &middot;&middot;&middot;
            </button>
            {mobileMenuOpen && (
              <div className="mobile-menu-dropdown">
                {assetCtx && (
                  <button
                    className="mobile-menu-item"
                    onClick={() => { setMobileMenuOpen(false); assetCtx.openProfileFlow() }}
                  >
                    Profile
                  </button>
                )}
                {authStatus === 'authed' && (
                  <>
                    <Link to="/admin" className="mobile-menu-item" onClick={() => setMobileMenuOpen(false)}>
                      Admin
                    </Link>
                    <button
                      className="mobile-menu-item"
                      onClick={() => { setMobileMenuOpen(false); handleLogout() }}
                    >
                      Log out
                    </button>
                  </>
                )}
                {activeTab === 'feed' && (
                  <>
                    <button
                      className="mobile-menu-item"
                      onClick={() => { setMobileMenuOpen(false); onAboutOpen() }}
                    >
                      About
                    </button>
                    <Link to="/privacy" className="mobile-menu-item" onClick={() => setMobileMenuOpen(false)}>
                      Privacy Policy
                    </Link>
                    <Link to="/terms" className="mobile-menu-item" onClick={() => setMobileMenuOpen(false)}>
                      Terms of Use
                    </Link>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Live dot */}
          <span className="live-indicator" aria-label="Live data feed active">
            <span className="live-dot" aria-hidden="true" />
            LIVE
          </span>

          {/* Clock — clicking opens timezone popover */}
          <div className="tz-wrap" ref={popoverRef}>
            <button
              className="header-clock-btn"
              onClick={() => setPopoverOpen(v => !v)}
              aria-label="Select timezone — currently showing time in selected timezone"
              aria-expanded={popoverOpen}
            >
              {localTime && tzAbbr ? (
                <>
                  <span className="clock-local">{localTime} {tzAbbr}</span>
                  <span className="clock-sep">  /  </span>
                  <span className="clock-utc">{utcTime} UTC</span>
                </>
              ) : (
                <span className="clock-utc">{utcTime} UTC</span>
              )}
            </button>

            {/* Timezone popover */}
            {popoverOpen && (
              <div className="tz-popover" role="dialog" aria-label="Timezone selector">
                <input
                  type="search"
                  className="tz-search mono"
                  placeholder="Search timezone..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  autoFocus
                  aria-label="Search timezones"
                />
                <ul className="tz-list" role="listbox" aria-label="Available timezones">
                  {filtered.map(t => {
                    const abbr = getTzAbbr(t.tz, now)
                    const time = formatTime(now, t.tz)
                    const active = tz === t.tz
                    return (
                      <li
                        key={t.tz}
                        className={`tz-item${active ? ' tz-item-active' : ''}`}
                        role="option"
                        aria-selected={active}
                        onClick={() => selectTz(t.tz)}
                      >
                        <span className="tz-item-abbr mono">{abbr}</span>
                        <span className="tz-item-time mono">{time}</span>
                        <span className="tz-item-name">{t.tz}</span>
                      </li>
                    )
                  })}
                  {filtered.length === 0 && (
                    <li className="tz-empty mono">No match for "{search}"</li>
                  )}
                </ul>
              </div>
            )}
          </div>

        </div>
      </div>
    </header>
    {activeTab !== null && (
      <nav className="mobile-tab-bar" aria-label="Main navigation">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`mobile-tab${activeTab === t.id ? ' active' : ''}`}
            onClick={() => onTabChange(t.id)}
            aria-label={t.aria}
            aria-current={activeTab === t.id ? 'page' : undefined}
          >
            {t.label}
          </button>
        ))}
      </nav>
    )}
    </>
  )
}
