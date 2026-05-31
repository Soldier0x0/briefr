import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import './Header.css'

function utcClock() {
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  return `${now.getUTCFullYear()}-${pad(now.getUTCMonth() + 1)}-${pad(now.getUTCDate())} ${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())} UTC`
}

export default function Header({ activeTab, onTabChange, onAboutOpen }) {
  const [clock, setClock] = useState(utcClock)

  useEffect(() => {
    const id = setInterval(() => setClock(utcClock()), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <header className="header" role="banner">
      <div className="header-inner">
        {/* Left: logo (clickable → about) */}
        <div className="header-left">
          <button
            className="header-logo-btn"
            onClick={onAboutOpen}
            aria-label="Open about VEKTOR"
          >
            VEKTOR
          </button>
          <span className="header-divider" aria-hidden="true">//</span>
          <span className="header-tagline">CVE intelligence</span>
        </div>

        {/* Center: nav tabs (only shown on feed pages) */}
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

        {/* Right: legal links, live dot, clock */}
        <div className="header-right">
          <nav className="header-legal" aria-label="Legal links">
            <button
              className="header-legal-link"
              onClick={onAboutOpen}
              aria-label="About VEKTOR"
            >
              About
            </button>
            <span className="header-legal-sep" aria-hidden="true">&middot;</span>
            <Link
              to="/privacy"
              className="header-legal-link"
              aria-label="Privacy Policy"
            >
              Privacy
            </Link>
            <span className="header-legal-sep" aria-hidden="true">&middot;</span>
            <Link
              to="/terms"
              className="header-legal-link"
              aria-label="Terms of Service"
            >
              Terms
            </Link>
          </nav>

          <span className="live-indicator" aria-label="Live data feed active">
            <span className="live-dot" aria-hidden="true" />
            LIVE
          </span>
          <time className="header-clock" aria-label="Current UTC time" dateTime={new Date().toISOString()}>
            {clock}
          </time>
        </div>
      </div>
    </header>
  )
}
