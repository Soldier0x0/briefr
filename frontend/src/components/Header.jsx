import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useAssetProfileOptional } from '../context/AssetProfileContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import ShortcutsPanel from './ShortcutsPanel.jsx'
import UserMenu from './UserMenu.jsx'
import ApiQueueIndicator from './ApiQueueIndicator.jsx'
import NotificationBell from './NotificationBell.jsx'
import HeaderClock from './HeaderClock.jsx'
import './Header.css'
import { feedHealthLevel, feedHealthLabel } from '../utils/feedHealthStatus.js'

export default function Header({ activeTab, onTabChange, onAboutOpen, onTutorialOpen, onLogoClick, onTimezoneChange, showShortcuts, feedHealth = null }) {
  const assetCtx = useAssetProfileOptional()
  const { status: authStatus } = useAuth()
  const [overflowOpen, setOverflowOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const overflowRef                     = useRef(null)

  useEffect(() => {
    function onDown(e) {
      if (overflowOpen && overflowRef.current && !overflowRef.current.contains(e.target)) {
        setOverflowOpen(false)
        setShortcutsOpen(false)
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [overflowOpen])

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
            <Link
              to="/security-architecture"
              className="header-tab"
              aria-label="Go to Security Architecture"
            >
              ARCH
            </Link>
          </nav>
        )}

        {/* Right: overflow, queue, account, clock */}
        <div className="header-right">
          <ApiQueueIndicator apiQueue={feedHealth?.api_queue} />

          {authStatus === 'authed' ? (
            <NotificationBell scope="analyst" className="header-notification-bell" />
          ) : null}

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
                      onClick={() => { setOverflowOpen(false); onTutorialOpen?.() }}
                    >
                      Show tutorial again
                    </button>
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

          <HeaderClock onTimezoneChange={onTimezoneChange} />

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
        <Link to="/security-architecture" className="mobile-tab" aria-label="Go to Security Architecture">
          ARCH
        </Link>
      </nav>
    )}
    </>
  )
}
