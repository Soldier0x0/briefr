import { useState, useEffect } from 'react'
import './Header.css'

function utcClock() {
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  return `${now.getUTCFullYear()}-${pad(now.getUTCMonth() + 1)}-${pad(now.getUTCDate())} ${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())} UTC`
}

export default function Header({ activeTab, onTabChange }) {
  const [clock, setClock] = useState(utcClock)

  useEffect(() => {
    const id = setInterval(() => setClock(utcClock()), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <header className="header" role="banner">
      <div className="header-inner">
        <div className="header-left">
          <span className="header-logo" aria-label="VEKTOR">VEKTOR</span>
          <span className="header-divider" aria-hidden="true">//</span>
          <span className="header-tagline">CVE intelligence</span>
        </div>

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

        <div className="header-right">
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
