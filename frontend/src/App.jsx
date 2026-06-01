import { useState, useEffect, useCallback, useRef } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Header from './components/Header.jsx'
import Hero from './components/Hero.jsx'
import StatsRow from './components/StatsRow.jsx'
import CVEFeed from './components/CVEFeed.jsx'
import Sidebar from './components/Sidebar.jsx'
import IOCLookup from './components/IOCLookup.jsx'
import DetailDrawer from './components/DetailDrawer.jsx'
import DigestModal from './components/DigestModal.jsx'
import AboutModal from './components/AboutModal.jsx'
import ShortcutsPanel from './components/ShortcutsPanel.jsx'
import PrivacyPage from './pages/PrivacyPage.jsx'
import TermsPage from './pages/TermsPage.jsx'
import { fetchStats, fetchHealth } from './api.js'
import { formatAbsolute, getTzAbbr } from './utils/timezone.js'

const DEFAULT_FILTERS = {
  severity: null,
  kev_only: false,
  poc_only: false,
  epss_min: null,
  search: '',
  stack: '',
}

// ── Last-refreshed helper ─────────────────────────────────
function timeAgoMinutes(sqliteUtc) {
  if (!sqliteUtc) return null
  const date = new Date(sqliteUtc.replace(' ', 'T') + 'Z')
  const diff  = Math.floor((Date.now() - date.getTime()) / 60000)
  if (diff < 1)  return 'just now'
  if (diff < 60) return `${diff} minute${diff === 1 ? '' : 's'} ago`
  const h = Math.floor(diff / 60)
  if (h < 24)    return `${h} hour${h === 1 ? '' : 's'} ago`
  return `${Math.floor(h / 24)} days ago`
}

function formatScheduleLabel(schedule) {
  if (!schedule) return null
  const hh = String(schedule.hour).padStart(2, '0')
  const mm = String(schedule.minute).padStart(2, '0')
  return `${hh}:${mm} ${getTzAbbr(schedule.timezone)}`
}

function FeedRefreshStatus({ lastUpdated, nextRefreshUtc, timezone, refreshSchedule }) {
  const [, tick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => tick(n => n + 1), 60000)
    return () => clearInterval(id)
  }, [])

  const lastLabel = timeAgoMinutes(lastUpdated)
  const nextUtcLabel = nextRefreshUtc ? formatAbsolute(nextRefreshUtc, 'UTC') : null
  const nextUserLabel =
    nextRefreshUtc && timezone ? formatAbsolute(nextRefreshUtc, timezone) : null
  const scheduleLabel = formatScheduleLabel(refreshSchedule)

  if (!lastLabel && !nextUtcLabel) return null

  return (
    <p className="last-refreshed mono" aria-live="polite">
      {lastLabel && <span>Last refreshed {lastLabel}</span>}
      {lastLabel && nextUtcLabel && <span> · </span>}
      {nextUtcLabel && (
        <span>
          Next refresh at {nextUtcLabel}
          {nextUserLabel && timezone !== 'UTC' && <> · {nextUserLabel}</>}
          {scheduleLabel && <> (auto daily {scheduleLabel})</>}
        </span>
      )}
    </p>
  )
}

function cycleFilter(filters) {
  if (!filters.kev_only && !filters.poc_only && !filters.severity) {
    return { ...filters, kev_only: true, poc_only: false, severity: null }
  }
  if (filters.kev_only) {
    return { ...filters, kev_only: false, poc_only: false, severity: 'CRITICAL' }
  }
  if (filters.severity === 'CRITICAL') {
    return { ...filters, kev_only: false, poc_only: true, severity: null }
  }
  return { ...filters, kev_only: false, poc_only: false, severity: null }
}

function MainApp({ stats, filters, setFilters, selectedCVE, setSelectedCVE,
                   digestOpen, setDigestOpen, digestCVEs, setDigestCVEs,
                   searchFocusTrigger, setSearchFocusTrigger, aboutOpen, setAboutOpen,
                   timezone, lastUpdated, nextRefreshUtc, refreshSchedule,
                   onDigestRequest }) {

  const handleBrief = useCallback((stack) => {
    setFilters(prev => ({ ...prev, stack }))
  }, [setFilters])

  const handleFiltersChange = useCallback((next) => {
    setFilters(prev => ({ ...prev, ...next }))
  }, [setFilters])

  const handleGenerateDigest = useCallback((cves) => {
    setDigestCVEs(cves)
    setDigestOpen(true)
  }, [setDigestCVEs, setDigestOpen])

  return (
    <>
      <Hero onBrief={handleBrief} />
      <StatsRow stats={stats} />
      <FeedRefreshStatus
        lastUpdated={lastUpdated}
        nextRefreshUtc={nextRefreshUtc}
        timezone={timezone}
        refreshSchedule={refreshSchedule}
      />
      <div className="content-grid">
        <CVEFeed
          filters={filters}
          onFiltersChange={handleFiltersChange}
          onSelectCVE={setSelectedCVE}
          onGenerateDigest={handleGenerateDigest}
          onDigestRequest={onDigestRequest}
          searchFocusTrigger={searchFocusTrigger}
          timezone={timezone}
        />
        <Sidebar filters={filters} onFiltersChange={handleFiltersChange} stats={stats} />
      </div>
    </>
  )
}

function FeedShortcuts() {
  return <ShortcutsPanel />
}

export default function App() {
  const location = useLocation()
  const [activeTab, setActiveTab]               = useState('feed')
  const digestCVEsRef = useRef([])
  const generateDigestRef = useRef(null)
  const [filters, setFilters]                   = useState(DEFAULT_FILTERS)
  const [stats, setStats]                       = useState(null)
  const [selectedCVE, setSelectedCVE]           = useState(null)
  const [digestOpen, setDigestOpen]             = useState(false)
  const [digestCVEs, setDigestCVEs]             = useState([])
  const [searchFocusTrigger, setSearchFocusTrigger] = useState(0)
  const [aboutOpen, setAboutOpen]               = useState(false)
  const [timezone, setTimezone]                 = useState(() => {
    try { return localStorage.getItem('briefr_timezone') || 'UTC' } catch { return 'UTC' }
  })
  const [lastUpdated, setLastUpdated]           = useState(null)
  const [nextRefreshUtc, setNextRefreshUtc]     = useState(null)
  const [refreshSchedule, setRefreshSchedule]   = useState(null)

  const loadHealth = useCallback(() => {
    fetchHealth(timezone)
      .then(h => {
        setLastUpdated(h.last_updated ?? null)
        setNextRefreshUtc(h.next_refresh_at_utc ?? null)
        setRefreshSchedule(h.refresh_schedule ?? null)
      })
      .catch(() => {})
  }, [timezone])

  useEffect(() => {
    fetchStats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => {
    loadHealth()
    const id = setInterval(loadHealth, 60000)
    return () => clearInterval(id)
  }, [loadHealth])

  // Keep timezone state in sync when Header dispatches changes
  useEffect(() => {
    const handler = (e) => setTimezone(e.detail)
    window.addEventListener('briefr-timezone-change', handler)
    return () => window.removeEventListener('briefr-timezone-change', handler)
  }, [])

  const handleGenerateDigest = useCallback((cves) => {
    setDigestCVEs(cves)
    digestCVEsRef.current = cves
    setDigestOpen(true)
  }, [])

  const registerDigestHandler = useCallback((fn) => {
    generateDigestRef.current = fn
  }, [])

  // ── Global keyboard shortcuts ─────────────────────────────
  useEffect(() => {
    let gPending = false
    let gTimer = null

    function handleKey(e) {
      if (e.key === 'Escape') {
        if (aboutOpen)    { setAboutOpen(false);  return }
        if (selectedCVE)  { setSelectedCVE(null); return }
        if (digestOpen)   { setDigestOpen(false); return }
        return
      }
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      if (e.key === '/') { e.preventDefault(); setSearchFocusTrigger(n => n + 1) }
      if (e.key === 'f' || e.key === 'F') setFilters(cycleFilter)

      if (e.key === 'g' || e.key === 'G') {
        gPending = true
        if (gTimer) clearTimeout(gTimer)
        gTimer = setTimeout(() => { gPending = false }, 800)
        return
      }
      if ((e.key === 'd' || e.key === 'D') && gPending) {
        gPending = false
        if (gTimer) clearTimeout(gTimer)
        e.preventDefault()
        if (generateDigestRef.current) {
          generateDigestRef.current()
        } else if (digestCVEsRef.current.length) {
          handleGenerateDigest(digestCVEsRef.current)
        }
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('keydown', handleKey)
      if (gTimer) clearTimeout(gTimer)
    }
  }, [aboutOpen, selectedCVE, digestOpen, handleGenerateDigest])

  const showFeedShortcuts =
    location.pathname !== '/privacy' &&
    location.pathname !== '/terms' &&
    activeTab === 'feed'

  return (
    <div className="app">
      <Routes>
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms"   element={<TermsPage />} />
        <Route path="*" element={
          <>
            <Header
              activeTab={activeTab}
              onTabChange={setActiveTab}
              onAboutOpen={() => setAboutOpen(true)}
              onTimezoneChange={setTimezone}
            />

            <div className="app-main">
              {activeTab === 'feed' && (
                <MainApp
                  stats={stats}
                  filters={filters}
                  setFilters={setFilters}
                  selectedCVE={selectedCVE}
                  setSelectedCVE={setSelectedCVE}
                  digestOpen={digestOpen}
                  setDigestOpen={setDigestOpen}
                  digestCVEs={digestCVEs}
                  setDigestCVEs={setDigestCVEs}
                  searchFocusTrigger={searchFocusTrigger}
                  setSearchFocusTrigger={setSearchFocusTrigger}
                  aboutOpen={aboutOpen}
                  setAboutOpen={setAboutOpen}
                  timezone={timezone}
                  lastUpdated={lastUpdated}
                  nextRefreshUtc={nextRefreshUtc}
                  refreshSchedule={refreshSchedule}
                  onDigestRequest={registerDigestHandler}
                />
              )}
              {activeTab === 'ioc' && <IOCLookup />}
            </div>

            {showFeedShortcuts && <FeedShortcuts />}

            <footer className="app-footer" role="contentinfo">
              <div className="footer-left">
                <span>BRIEFR</span> // CVE intelligence platform // data from NVD, CISA, FIRST, OSV
              </div>
              <div className="footer-right" style={{ fontSize: '0.6875rem', color: 'var(--text3)' }}>
                All times UTC &mdash; not a substitute for professional security advice
              </div>
            </footer>


            <DetailDrawer cve={selectedCVE} onClose={() => setSelectedCVE(null)} />

            {digestOpen && (
              <DigestModal cves={digestCVEs} filters={filters} onClose={() => setDigestOpen(false)} />
            )}

            {aboutOpen && (
              <AboutModal onClose={() => setAboutOpen(false)} />
            )}
          </>
        } />
      </Routes>
    </div>
  )
}
