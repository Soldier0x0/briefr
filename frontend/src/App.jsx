import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { InvestigationProvider } from './context/InvestigationContext.jsx'
import InvestigationPanel from './components/InvestigationPanel.jsx'
import Header from './components/Header.jsx'
import Hero from './components/Hero.jsx'
import StatsRow from './components/StatsRow.jsx'
import TimelineHeatmap from './components/TimelineHeatmap.jsx'
import CVEFeed from './components/CVEFeed.jsx'
import Sidebar from './components/Sidebar.jsx'
import IOCLookup from './components/IOCLookup.jsx'
import AIThreats from './components/AIThreats.jsx'
import DetailDrawer from './components/DetailDrawer.jsx'
import DigestModal from './components/DigestModal.jsx'
import AboutModal from './components/AboutModal.jsx'
import PrivacyPage from './pages/PrivacyPage.jsx'
import TermsPage from './pages/TermsPage.jsx'
import { fetchStats, fetchHealth, fetchCVE } from './api.js'
import { formatAbsolute, getTzAbbr } from './utils/timezone.js'
import { useInvestigation } from './context/InvestigationContext.jsx'
import './components/InvestigationPanel.css'

const DEFAULT_FILTERS = {
  severity: null,
  kev_only: false,
  poc_only: false,
  epss_min: null,
  search: '',
  stack: '',
  vendors: '',
  technique: '',
  published_on: '',
  my_stack_only: false,
  summary_only: false,
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

function formatIngestCadence(schedule) {
  if (!schedule) return null
  const parts = []
  if (schedule.nvd_interval_hours != null) {
    parts.push(`NVD every ${schedule.nvd_interval_hours}h`)
  }
  if (schedule.kev_interval_minutes != null) {
    parts.push(`KEV every ${schedule.kev_interval_minutes}m`)
  }
  if (schedule.epss_interval_hours != null) {
    parts.push(`EPSS every ${schedule.epss_interval_hours}h`)
  }
  const tz = schedule.timezone ? getTzAbbr(schedule.timezone) : ''
  const mitreH = schedule.mitre_weekly_hour ?? schedule.hour
  const mitreM = schedule.mitre_weekly_minute ?? schedule.minute
  if (mitreH != null && mitreM != null) {
    const hh = String(mitreH).padStart(2, '0')
    const mm = String(mitreM).padStart(2, '0')
    parts.push(`MITRE weekly Sun ${hh}:${mm}${tz ? ` ${tz}` : ''}`)
  }
  return parts.length ? parts.join(' · ') : null
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
  const cadenceLabel = formatIngestCadence(refreshSchedule)

  if (!lastLabel && !nextUtcLabel) return null

  return (
    <p className="last-refreshed mono" aria-live="polite">
      {lastLabel && <span>Last refreshed {lastLabel}</span>}
      {lastLabel && nextUtcLabel && <span> · </span>}
      {nextUtcLabel && (
        <span>
          Next refresh at {nextUtcLabel}
          {nextUserLabel && timezone !== 'UTC' && <> · {nextUserLabel}</>}
          {cadenceLabel && <> · {cadenceLabel}</>}
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
    setFilters(prev => ({ ...prev, stack: stack || '' }))
  }, [setFilters])

  const handleClearStack = useCallback(() => {
    setFilters(prev => ({ ...prev, stack: '' }))
  }, [setFilters])

  const handleFiltersChange = useCallback((next) => {
    setFilters(prev => ({ ...prev, ...next }))
  }, [setFilters])

  const handleGenerateDigest = useCallback((cves) => {
    setDigestCVEs(cves)
    setDigestOpen(true)
  }, [setDigestCVEs, setDigestOpen])

  const handleSelectCVE = useCallback((cve) => {
    setSelectedCVE(cve)
    fetchCVE(cve.cve_id)
      .then(full => setSelectedCVE(full))
      .catch(() => {})
  }, [setSelectedCVE])

  return (
    <>
      <Hero
        activeStack={filters.stack}
        onBrief={handleBrief}
        onClearStack={handleClearStack}
      />
      <StatsRow stats={stats} />
      <TimelineHeatmap filters={filters} onFiltersChange={handleFiltersChange} />
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
          onSelectCVE={handleSelectCVE}
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
  const [iocPrefill, setIocPrefill]             = useState(null)
  const [iocSessionKey, setIocSessionKey]       = useState(0)
  const [atlasActorFilter, setAtlasActorFilter] = useState(null)

  useEffect(() => {
    if (activeTab === 'feed') {
      setIocPrefill(null)
      setIocSessionKey(k => k + 1)
    }
  }, [activeTab])

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

  const openCveById = useCallback((cveId) => {
    fetchCVE(cveId)
      .then(full => setSelectedCVE(full))
      .catch(() => setSelectedCVE({ cve_id: cveId }))
  }, [])

  const investigationNav = useMemo(() => ({
    setActiveTab,
    clearIocPrefill: () => setIocPrefill(null),
    resetIocSession: () => setIocSessionKey(k => k + 1),
    setIocPrefill: (payload) => {
      if (typeof payload === 'string') {
        setIocPrefill({
          value: payload,
          indicators: [{ type: 'ip', value: payload }],
          trigger: Date.now(),
        })
        return
      }
      setIocPrefill({ ...payload, trigger: payload.trigger ?? Date.now() })
    },
    setAtlasActorFilter,
    clearAtlasFilter: () => setAtlasActorFilter(null),
    openCve: (cveId) => {
      setActiveTab('feed')
      openCveById(cveId)
    },
  }), [openCveById])

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
    <InvestigationProvider navigation={investigationNav}>
      <Routes>
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route
          path="*"
          element={(
            <AppLayout
              activeTab={activeTab}
              setActiveTab={setActiveTab}
              showFeedShortcuts={showFeedShortcuts}
              onAboutOpen={() => setAboutOpen(true)}
              onTimezoneChange={setTimezone}
              iocPrefill={iocPrefill}
              iocSessionKey={iocSessionKey}
              atlasActorFilter={atlasActorFilter}
              onClearAtlasFilter={() => setAtlasActorFilter(null)}
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
              openCveById={openCveById}
            />
          )}
        />
      </Routes>
    </InvestigationProvider>
  )
}

function AppLayout({
  activeTab,
  setActiveTab,
  showFeedShortcuts,
  onAboutOpen,
  onTimezoneChange,
  iocPrefill,
  iocSessionKey,
  atlasActorFilter,
  onClearAtlasFilter,
  stats,
  filters,
  setFilters,
  selectedCVE,
  setSelectedCVE,
  digestOpen,
  setDigestOpen,
  digestCVEs,
  setDigestCVEs,
  searchFocusTrigger,
  setSearchFocusTrigger,
  aboutOpen,
  setAboutOpen,
  timezone,
  lastUpdated,
  nextRefreshUtc,
  refreshSchedule,
  onDigestRequest,
  openCveById,
}) {
  const { showPanel, panelExpanded } = useInvestigation()
  const layoutClass = [
    'app',
    'app-layout',
    showPanel ? 'has-investigation' : '',
    showPanel && panelExpanded ? 'investigation-expanded' : '',
  ].filter(Boolean).join(' ')

  return (
    <div className={layoutClass}>
      <InvestigationPanel />
      <div className="app-shell">
        <Header
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onAboutOpen={onAboutOpen}
          onLogoClick={() => setActiveTab('feed')}
          onTimezoneChange={onTimezoneChange}
          showShortcuts={showFeedShortcuts}
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
                  onDigestRequest={onDigestRequest}
                />
              )}
              {activeTab === 'ioc' && (
                <IOCLookup key={iocSessionKey} prefill={iocPrefill} />
              )}
              {activeTab === 'atlas' && (
                <AIThreats
                  actorFilter={atlasActorFilter}
                  onClearActorFilter={onClearAtlasFilter}
                />
              )}
            </div>

            <footer className="app-footer" role="contentinfo">
              <div className="footer-left">
                <span>BRIEFR</span> // CVE intelligence platform // data from NVD, CISA, FIRST, OSV
              </div>
              <div className="footer-right" style={{ fontSize: '0.6875rem', color: 'var(--text3)' }}>
                All times UTC &mdash; not a substitute for professional security advice
              </div>
            </footer>


            <DetailDrawer
              cve={selectedCVE}
              onClose={() => setSelectedCVE(null)}
              onCveReplace={setSelectedCVE}
            />

            {digestOpen && (
              <DigestModal cves={digestCVEs} filters={filters} onClose={() => setDigestOpen(false)} />
            )}

            {aboutOpen && (
              <AboutModal onClose={() => setAboutOpen(false)} />
            )}
      </div>
    </div>
  )
}
