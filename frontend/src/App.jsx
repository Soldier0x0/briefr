import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { InvestigationProvider } from './context/InvestigationContext.jsx'
import { overlayDepth } from './hooks/useModalLayer.js'
import InvestigationPanel from './components/InvestigationPanel.jsx'
import Header from './components/Header.jsx'
import Hero from './components/Hero.jsx'
import StatsRow from './components/StatsRow.jsx'
import TimelineHeatmap from './components/TimelineHeatmap.jsx'
import WhatChangedPanel from './components/WhatChangedPanel.jsx'
import MorningBrief from './components/MorningBrief.jsx'
import CVEFeed from './components/CVEFeed.jsx'
import Sidebar from './components/Sidebar.jsx'
import IOCLookup from './components/IOCLookup.jsx'
import CaseStudies from './components/CaseStudies.jsx'
import Forge from './components/Forge.jsx'
import DetailDrawer from './components/DetailDrawer.jsx'
import DigestModal from './components/DigestModal.jsx'
import AboutModal from './components/AboutModal.jsx'
import PrivacyPage from './pages/PrivacyPage.jsx'
import TermsPage from './pages/TermsPage.jsx'
import { fetchStats, fetchHealth, fetchCVE } from './api.js'
import { useAssetProfileOptional } from './context/AssetProfileContext.jsx'
import {
  aiFrameworksQueryParam,
  getAiFrameworksForAlerts,
  hasDeclaredAiAssets,
} from './utils/aiAssets.js'
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
  ai_context_only: false,
  ai_profile_match: false,
  ai_profile: '',
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

function BriefView({ stats, filters, setFilters,
                    timezone, lastUpdated, nextRefreshUtc, refreshSchedule,
                    showAiAlerts, onAiAlertsClick, onOpenFullFeed, onSelectCVE }) {

  const handleBrief = useCallback((stack) => {
    setFilters(prev => ({ ...prev, stack: stack || '' }))
  }, [setFilters])

  const handleClearStack = useCallback(() => {
    setFilters(prev => ({ ...prev, stack: '' }))
  }, [setFilters])

  return (
    <>
      <Hero
        activeStack={filters.stack}
        onBrief={handleBrief}
        onClearStack={handleClearStack}
      />
      <StatsRow
        stats={stats}
        showAiAlerts={showAiAlerts}
        onAiAlertsClick={onAiAlertsClick}
      />
      <MorningBrief
        stack={filters.stack}
        onSelectCVE={onSelectCVE}
        onOpenFullFeed={onOpenFullFeed}
        timezone={timezone}
      />
      <WhatChangedPanel onSelectCVE={onSelectCVE} />
      <FeedRefreshStatus
        lastUpdated={lastUpdated}
        nextRefreshUtc={nextRefreshUtc}
        timezone={timezone}
        refreshSchedule={refreshSchedule}
      />
    </>
  )
}

function FeedView({ stats, filters, setFilters, selectedCVE, setSelectedCVE,
                   digestOpen, setDigestOpen, digestCVEs, setDigestCVEs,
                   searchFocusTrigger, setSearchFocusTrigger, aboutOpen, setAboutOpen,
                   timezone, lastUpdated, nextRefreshUtc, refreshSchedule,
                   onDigestRequest, showAiAlerts, onAiAlertsClick }) {

  const handleBrief = useCallback((stack) => {
    setFilters(prev => ({ ...prev, stack: stack || '' }))
  }, [setFilters])

  const handleClearStack = useCallback(() => {
    setFilters(prev => ({ ...prev, stack: '' }))
  }, [setFilters])

  const handleFiltersChange = useCallback((next) => {
    setFilters(prev => {
      // No-op guard: clicking the already-active filter must not produce a
      // new object identity (which would reset + refetch + scroll the feed).
      const changed = Object.keys(next).some(k => next[k] !== prev[k])
      return changed ? { ...prev, ...next } : prev
    })
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
      <StatsRow
        stats={stats}
        showAiAlerts={showAiAlerts}
        onAiAlertsClick={onAiAlertsClick}
      />
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
          overlayOpen={!!selectedCVE || digestOpen || aboutOpen}
        />
        <Sidebar filters={filters} onFiltersChange={handleFiltersChange} stats={stats} />
      </div>
    </>
  )
}

export default function App() {
  const location = useLocation()
  const [activeTab, setActiveTab]               = useState('brief')
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
  const assetCtx = useAssetProfileOptional()

  const loadStats = useCallback(() => {
    const frameworks = getAiFrameworksForAlerts(assetCtx?.profile)
    fetchStats({ frameworks }).then(setStats).catch(() => {})
  }, [assetCtx?.profile])

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
    loadStats()
  }, [loadStats])

  useEffect(() => {
    const onRefreshStats = () => loadStats()
    window.addEventListener('briefr-stack-change', onRefreshStats)
    window.addEventListener('briefr-profile-change', onRefreshStats)
    return () => {
      window.removeEventListener('briefr-stack-change', onRefreshStats)
      window.removeEventListener('briefr-profile-change', onRefreshStats)
    }
  }, [loadStats])

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

  const showAiAlerts = hasDeclaredAiAssets(assetCtx?.profile)

  const handleAiAlertsClick = useCallback(() => {
    const fw = aiFrameworksQueryParam(assetCtx?.profile)
    if (!fw) return
    setActiveTab('feed')
    setFilters(prev => ({
      ...prev,
      ai_context_only: true,
      ai_profile_match: true,
      ai_profile: fw,
      kev_only: false,
      poc_only: false,
      severity: null,
      search: '',
      stack: '',
    }))
  }, [assetCtx?.profile])

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
      setActiveTab('brief')
      openCveById(cveId)
    },
  }), [openCveById])

  // ── Global keyboard shortcuts ─────────────────────────────
  useEffect(() => {
    let gPending = false
    let gTimer = null

    function handleKey(e) {
      if (e.key === 'Escape') {
        // Close the topmost layer only; one keypress never closes two layers.
        // PDF modal / shortcuts panel own their Escape — stand down for them.
        if (overlayDepth() > 0) return
        if (digestOpen)   { setDigestOpen(false); return }
        if (aboutOpen)    { setAboutOpen(false);  return }
        if (selectedCVE)  { setSelectedCVE(null); return }
        return
      }
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      // Feed shortcuts must not act behind an open overlay (drawer / digest /
      // about / PDF modal) — F used to silently change filters under the drawer.
      if (selectedCVE || digestOpen || aboutOpen || overlayDepth() > 0) return

      // Feed-only shortcuts (/, F, g+d digest).
      if (activeTab !== 'feed') return

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
  }, [aboutOpen, selectedCVE, digestOpen, handleGenerateDigest, activeTab])

  const showFeedShortcuts =
    location.pathname !== '/privacy' &&
    location.pathname !== '/terms' &&
    activeTab === 'feed'

  const handleSelectCVE = useCallback((cve) => {
    setSelectedCVE(cve)
    fetchCVE(cve.cve_id)
      .then(full => setSelectedCVE(full))
      .catch(() => {})
  }, [])

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
              showAiAlerts={showAiAlerts}
              onAiAlertsClick={handleAiAlertsClick}
              onSelectCVE={handleSelectCVE}
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
  showAiAlerts,
  onAiAlertsClick,
  onSelectCVE,
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
          onLogoClick={() => setActiveTab('brief')}
          onTimezoneChange={onTimezoneChange}
          showShortcuts={showFeedShortcuts}
        />

        <div className="app-main">
          {activeTab === 'brief' && (
            <BriefView
              stats={stats}
              filters={filters}
              setFilters={setFilters}
              timezone={timezone}
              lastUpdated={lastUpdated}
              nextRefreshUtc={nextRefreshUtc}
              refreshSchedule={refreshSchedule}
              showAiAlerts={showAiAlerts}
              onAiAlertsClick={onAiAlertsClick}
              onOpenFullFeed={() => setActiveTab('feed')}
              onSelectCVE={onSelectCVE}
            />
          )}
          {activeTab === 'feed' && (
            <FeedView
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
                  showAiAlerts={showAiAlerts}
                  onAiAlertsClick={onAiAlertsClick}
                />
              )}
              {activeTab === 'ioc' && (
                <IOCLookup key={iocSessionKey} prefill={iocPrefill} />
              )}
              {activeTab === 'atlas' && (
                <CaseStudies
                  initialSearch={atlasActorFilter || ''}
                  onClearFilter={onClearAtlasFilter}
                />
              )}
              {activeTab === 'forge' && <Forge />}
            </div>

            {activeTab !== 'feed' && activeTab !== 'brief' && (
              <footer className="app-footer" role="contentinfo">
                <div className="footer-left">
                  <span>BRIEFR</span> // CVE intelligence platform
                  <span className="footer-copyright mono">
                    &copy; 2026 BRIEFR &middot; Proprietary &middot; All Rights Reserved
                  </span>
                </div>
                <div className="footer-right" style={{ fontSize: '0.6875rem', color: 'var(--text3)' }}>
                  All times UTC &mdash; not a substitute for professional security advice
                </div>
              </footer>
            )}


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
