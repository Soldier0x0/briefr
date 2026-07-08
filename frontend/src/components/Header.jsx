import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useAssetProfileOptional } from '../context/AssetProfileContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import ShortcutsPanel from './ShortcutsPanel.jsx'
import UserMenu from './UserMenu.jsx'
import ApiQueueIndicator from './ApiQueueIndicator.jsx'
import {
  COMMON_TIMEZONES,
  formatTime,
  getTimezone,
  getTzAbbr,
  getTzOffsetLabel,
  setTimezone as persistTimezone,
} from '../utils/timezone.js'
import './Header.css'
import { feedHealthLevel, feedHealthLabel } from '../utils/feedHealthStatus.js'

export default function Header({ activeTab, onTabChange, onAboutOpen, onLogoClick, onTimezoneChange, showShortcuts, feedHealth = null }) {
  const assetCtx = useAssetProfileOptional()
  const { status: authStatus } = useAuth()
  const [now, setNow]               = useState(new Date())
  const [tz, setTz]                 = useState(() => getTimezone())
  const [popoverOpen, setPopoverOpen]   = useState(false)
  const [overflowOpen, setOverflowOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [search, setSearch]             = useState('')
  const popoverRef                      = useRef(null)
  const overflowRef                     = useRef(null)

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
      if (overflowOpen && overflowRef.current && !overflowRef.current.contains(e.target)) {
        setOverflowOpen(false)
        setShortcutsOpen(false)
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [popoverOpen, overflowOpen])

  useEffect(() => {
    const onTz = (e) => setTz(e.detail)
    const onLoaded = (e) => setTz(e.detail?.timezone || getTimezone())
    window.addEventListener('briefr-timezone-change', onTz)
    window.addEventListener('briefr-preferences-loaded', onLoaded)
    return () => {
      window.removeEventListener('briefr-timezone-change', onTz)
      window.removeEventListener('briefr-preferences-loaded', onLoaded)
    }
  }, [])

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
        getTzAbbr(t.tz, now).toLowerCase().includes(q) ||
        getTzOffsetLabel(t.tz, now).includes(q)
      )
    : COMMON_TIMEZONES

  const feedLevel = feedHealthLevel(feedHealth)
  const feedLabel = feedHealthLabel(feedLevel)

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
          {feedHealth && (
            <span
              className={`live-indicator live-indicator--dot-only live-indicator--${feedLevel}`}
              aria-label={feedLabel}
              title={feedLabel}
            >
              <span className="live-dot" aria-hidden="true" />
            </span>
          )}
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

        {/* Right: overflow, queue, account, clock */}
        <div className="header-right">
          <ApiQueueIndicator apiQueue={feedHealth?.api_queue} />

          {authStatus === 'authed' ? (
            <UserMenu
              onMyStack={assetCtx ? assetCtx.openProfileFlow : undefined}
              onClearSession={assetCtx?.isLoaded ? assetCtx.clearProfile : undefined}
              showClearSession={!!assetCtx?.isLoaded}
            />
          ) : null}

          <div className="header-overflow-wrap" ref={overflowRef}>
            <button
              className="header-overflow-btn"
              onClick={() => {
                setOverflowOpen(v => !v)
                if (overflowOpen) setShortcutsOpen(false)
              }}
              aria-label="Open menu"
              aria-expanded={overflowOpen}
            >
              &middot;&middot;&middot;
            </button>
            {overflowOpen && (
              <div className="header-overflow-dropdown" role="menu" aria-label="More options">
                {shortcutsOpen ? (
                  <ShortcutsPanel
                    listOnly
                    onClose={() => setShortcutsOpen(false)}
                  />
                ) : (
                  <>
                    {assetCtx && authStatus !== 'authed' && (
                      <button
                        type="button"
                        className="header-overflow-item"
                        role="menuitem"
                        onClick={() => {
                          setOverflowOpen(false)
                          assetCtx.openProfileFlow()
                        }}
                      >
                        My Stack
                      </button>
                    )}
                    {assetCtx?.isLoaded && authStatus !== 'authed' && (
                      <button
                        type="button"
                        className="header-overflow-item"
                        role="menuitem"
                        onClick={() => {
                          setOverflowOpen(false)
                          assetCtx.clearProfile()
                        }}
                      >
                        Clear session
                      </button>
                    )}
                    {showShortcuts && (
                      <button
                        type="button"
                        className="header-overflow-item"
                        role="menuitem"
                        onClick={() => setShortcutsOpen(true)}
                      >
                        Keyboard shortcuts
                      </button>
                    )}
                    <button
                      type="button"
                      className="header-overflow-item"
                      role="menuitem"
                      onClick={() => { setOverflowOpen(false); onAboutOpen?.() }}
                    >
                      About
                    </button>
                    <Link
                      to="/privacy"
                      className="header-overflow-item"
                      role="menuitem"
                      onClick={() => setOverflowOpen(false)}
                    >
                      Privacy Policy
                    </Link>
                    <Link
                      to="/terms"
                      className="header-overflow-item"
                      role="menuitem"
                      onClick={() => setOverflowOpen(false)}
                    >
                      Terms of Use
                    </Link>
                  </>
                )}
              </div>
            )}
          </div>

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
                    const offset = getTzOffsetLabel(t.tz, now)
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
                        <span className="tz-item-offset mono">{offset}</span>
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
