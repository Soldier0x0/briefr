import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { triggerRefresh } from '../api.js'
import {
  COMMON_TIMEZONES,
  formatTime,
  getTzAbbr,
  setTimezone as persistTimezone,
} from '../utils/timezone.js'
import './Header.css'

// ── Theme helpers ─────────────────────────────────────────
function getCurrentTheme() {
  return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark'
}

function applyTheme(theme) {
  if (theme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light')
  } else {
    document.documentElement.removeAttribute('data-theme')
  }
  try { localStorage.setItem('vektor_theme', theme) } catch {}
}

export default function Header({ activeTab, onTabChange, onAboutOpen, onTimezoneChange }) {
  const [now, setNow]               = useState(new Date())
  const [theme, setTheme]           = useState(getCurrentTheme)
  const [tz, setTz]                 = useState(() => {
    try { return localStorage.getItem('vektor_timezone') || 'UTC' } catch { return 'UTC' }
  })
  const [popoverOpen, setPopoverOpen] = useState(false)
  const [search, setSearch]         = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const popoverRef                  = useRef(null)

  // Tick every second
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  // Close popover on outside click
  useEffect(() => {
    if (!popoverOpen) return
    function onDown(e) {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        setPopoverOpen(false)
        setSearch('')
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [popoverOpen])

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    applyTheme(next)
    setTheme(next)
  }

  function selectTz(newTz) {
    setTz(newTz)
    persistTimezone(newTz)
    if (onTimezoneChange) onTimezoneChange(newTz)
    setPopoverOpen(false)
    setSearch('')
  }

  async function handleRefresh() {
    if (refreshing) return
    setRefreshing(true)
    try { await triggerRefresh() } catch {}
    setTimeout(() => setRefreshing(false), 3000)
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

  return (
    <header className="header" role="banner">
      <div className="header-inner">
        {/* Left: logo */}
        <div className="header-left">
          <button className="header-logo-btn" onClick={onAboutOpen} aria-label="Open about VEKTOR">
            VEKTOR
          </button>
          <span className="header-divider" aria-hidden="true">//</span>
          <span className="header-tagline">CVE intelligence</span>
        </div>

        {/* Center: tabs */}
        {activeTab !== null && (
          <nav className="header-nav" aria-label="Main navigation">
            <button
              className={`header-tab${activeTab === 'feed' ? ' active' : ''}`}
              onClick={() => onTabChange('feed')}
              aria-label="Switch to CVE brief feed"
              aria-current={activeTab === 'feed' ? 'page' : undefined}
            >
              BRIEF
            </button>
            <button
              className={`header-tab${activeTab === 'ioc' ? ' active' : ''}`}
              onClick={() => onTabChange('ioc')}
              aria-label="Switch to IOC lookup"
              aria-current={activeTab === 'ioc' ? 'page' : undefined}
            >
              IOC LOOKUP
            </button>
          </nav>
        )}

        {/* Right: theme toggle, legal, live dot, clock, refresh */}
        <div className="header-right">
          {/* Theme toggle */}
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            ◐
          </button>

          {/* Legal links */}
          <nav className="header-legal" aria-label="Legal links">
            <button className="header-legal-link" onClick={onAboutOpen} aria-label="About VEKTOR">
              About
            </button>
            <span className="header-legal-sep" aria-hidden="true">&middot;</span>
            <Link to="/privacy" className="header-legal-link">Privacy</Link>
            <span className="header-legal-sep" aria-hidden="true">&middot;</span>
            <Link to="/terms" className="header-legal-link">Terms</Link>
          </nav>

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

          {/* Manual refresh */}
          <button
            className="header-refresh-btn"
            onClick={handleRefresh}
            disabled={refreshing}
            aria-label={refreshing ? 'Refresh in progress' : 'Manually trigger data refresh'}
          >
            {refreshing ? 'REFRESHING...' : '↻ REFRESH'}
          </button>
        </div>
      </div>
    </header>
  )
}
