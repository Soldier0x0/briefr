import { useState, useEffect, useCallback, useRef, useMemo, Suspense } from 'react'
import { Routes, Route, useLocation, Link, useSearchParams, Navigate } from 'react-router-dom'
import { InvestigationProvider } from './context/InvestigationContext.jsx'
import { overlayDepth } from './hooks/useModalLayer.js'
import { shouldIgnoreGlobalShortcut } from './utils/keyboardScope.js'
import { clearStalePointerState } from './utils/clearPointerState.js'
import Header from './components/Header.jsx'
import Hero from './components/Hero.jsx'
import StatsRow from './components/StatsRow.jsx'
import Sidebar from './components/Sidebar.jsx'
import DigestModal from './components/DigestModal.jsx'
import AboutModal from './components/AboutModal.jsx'
import TutorialOverlay from './components/TutorialOverlay.jsx'
import ToolErrorBoundary from './components/ToolErrorBoundary.jsx'
import CommandPalette from './components/CommandPalette.jsx'
import PrivacyPage from './pages/PrivacyPage.jsx'
import TermsPage from './pages/TermsPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import RequireAuth from './components/RequireAuth.jsx'
import RequireAdmin from './components/RequireAdmin.jsx'
import { useToast } from './components/Toast.jsx'
import { fetchStats, fetchHealth, fetchCVE } from './api.js'
import { useWatchlist } from './hooks/useWatchlist.js'
import { useAssetProfileOptional } from './context/AssetProfileContext.jsx'
import {
  aiFrameworksQueryParam,
  getAiFrameworksForAlerts,
  hasDeclaredAiAssets,
} from './utils/aiAssets.js'
import { formatAbsolute, getTimezone } from './utils/timezone.js'
import { createCveDrawerController } from './utils/openCveDrawer.js'
import { lazyWithReload } from './utils/lazyWithReload.js'
import { ingestLogUrl } from './utils/adminLinks.js'
import { getSavedStack } from './utils/cveFilters.js'
import { hasTutorialSeen, markTutorialSeen } from './utils/tutorial.js'
import { useInvestigation } from './context/InvestigationContext.jsx'
import useVisibilityAwareInterval from './hooks/useVisibilityAwareInterval.js'
import { resolveAppTab, buildAppTabSearchParams } from './utils/shellUrlState.js'
import { pushContext, replaceHygiene } from './utils/navHistory.js'

const BriefCharts = lazyWithReload(() => import('./components/BriefCharts.jsx'))
const MorningBrief = lazyWithReload(() => import('./components/MorningBrief.jsx'))
const TimelineHeatmap = lazyWithReload(() => import('./components/TimelineHeatmap.jsx'))
const WhatChangedPanel = lazyWithReload(() => import('./components/WhatChangedPanel.jsx'))
const CVEFeed = lazyWithReload(() => import('./components/CVEFeed.jsx'))
const InvestigationPanel = lazyWithReload(() => import('./components/InvestigationPanel.jsx'))
const IOCLookup = lazyWithReload(() => import('./components/IOCLookup.jsx'))
const CaseStudies = lazyWithReload(() => import('./components/CaseStudies.jsx'))
const Forge = lazyWithReload(() => import('./components/Forge.jsx'))
const DetailDrawer = lazyWithReload(() => import('./components/DetailDrawer'))
const AdminPage = lazyWithReload(() => import('./pages/admin/AdminPage.jsx'))
const WallboardPage = lazyWithReload(() => import('./pages/WallboardPage.jsx'))

/** PM-4c: legacy ARCH URL → Admin Security posture (preserve known sections). */
const POSTURE_REDIRECT_SECTIONS = new Set([
  'overview',
  'system_architecture',
  'trust_boundaries',
  'attack_surface',
  'risks',
])

function SecurityArchitectureRedirect() {
  const [searchParams] = useSearchParams()
  const sectionRaw = searchParams.get('section') || 'overview'
  const section = POSTURE_REDIRECT_SECTIONS.has(sectionRaw) ? sectionRaw : 'overview'
  const next = new URLSearchParams()
  next.set('p', 'securityposture')
  next.set('section', section)
  const node = searchParams.get('node')
  if (node && section === 'system_architecture') next.set('node', node)
  for (const key of ['type', 'status', 'severity', 'origin']) {
    const value = searchParams.get(key)
    if (value) next.set(key, value)
  }
  return <Navigate to={`/admin?${next.toString()}`} replace />
}

function TabLoading({ label }) {
  return (
    <p className="brief-charts-loading mono" aria-live="polite">
      Loading {label}…
    </p>
  )
}

const DEFAULT_FILTERS = {
  severity: null,
  kev_only: false,
  kev_overdue_only: false,
  poc_only: false,
  patch_only: false,
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
  watchlist_only: false,
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

function FeedRefreshStatus({ lastUpdated, nextRefreshUtc, timezone, feedHealth, tickEnabled = true }) {
  const [, tick] = useState(0)
  useVisibilityAwareInterval(() => tick(n => n + 1), 60000, { enabled: tickEnabled })

  const lastLabel = timeAgoMinutes(lastUpdated)
  const nextUtcLabel = nextRefreshUtc ? formatAbsolute(nextRefreshUtc, 'UTC') : null
  const nextUserLabel =
    nextRefreshUtc && timezone ? formatAbsolute(nextRefreshUtc, timezone) : null

  if (!lastLabel && !nextUtcLabel) return null

  return (
    <p className="last-refreshed mono" aria-live="polite">
      {lastLabel && <span>Last refreshed {lastLabel}</span>}
      {lastLabel && nextUtcLabel && <span> · </span>}
      {nextUtcLabel && (
        <span>
          Next refresh at {nextUtcLabel}
          {nextUserLabel && timezone !== 'UTC' && <> · {nextUserLabel}</>}
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

function BriefView({ isActive, stats, statsError, statsErrorRequestId, onRetryStats, filters, setFilters,
                    timezone, lastUpdated, nextRefreshUtc,
                    showAiAlerts, onAiAlertsClick, onStatTileClick, onOpenFullFeed, onSelectCVE,
                    feedHealth }) {

  const [queueReasonFilter, setQueueReasonFilter] = useState('all')
  const [queueDueWindow, setQueueDueWindow] = useState(null)

  const handleFiltersChange = useCallback((next) => {
    setFilters(prev => {
      const changed = Object.keys(next).some(k => next[k] !== prev[k])
      return changed ? { ...prev, ...next } : prev
    })
  }, [setFilters])

  const handleReasonFilterChange = useCallback((id) => {
    setQueueReasonFilter(id)
    if (id !== 'kev_due_soon') {
      setQueueDueWindow(null)
    }
  }, [])

  const handleDueWindowClear = useCallback(() => {
    setQueueDueWindow(null)
  }, [])

  return (
    <>
      <Hero />
      <StatsRow
        stats={stats}
        error={statsError}
        errorRequestId={statsErrorRequestId}
        onRetry={onRetryStats}
        showAiAlerts={showAiAlerts}
        onAiAlertsClick={onAiAlertsClick}
        onStatTileClick={onStatTileClick}
      />
      <Suspense
        fallback={
          <p className="brief-charts-loading mono" aria-live="polite">Loading morning brief…</p>
        }
      >
        <MorningBrief
          stack={filters.stack}
          onSelectCVE={onSelectCVE}
          onOpenFullFeed={onOpenFullFeed}
          reasonFilter={queueReasonFilter}
          onReasonFilterChange={handleReasonFilterChange}
          dueWindow={queueDueWindow}
          onDueWindowClear={handleDueWindowClear}
          fetchEnabled={isActive}
        />
      </Suspense>
      <Suspense
        fallback={
          <p className="brief-charts-loading mono" aria-live="polite">
            Loading charts…
          </p>
        }
      >
        <BriefCharts
          onSelectCVE={onSelectCVE}
          pollEnabled={isActive}
        />
      </Suspense>
      <div className="brief-intel-row">
        <Suspense fallback={null}>
          <TimelineHeatmap
            filters={filters}
            onFiltersChange={handleFiltersChange}
            fetchEnabled={isActive}
          />
        </Suspense>
        <Suspense fallback={null}>
          <WhatChangedPanel onSelectCVE={onSelectCVE} fetchEnabled={isActive} />
        </Suspense>
      </div>
      <FeedRefreshStatus
        lastUpdated={lastUpdated}
        nextRefreshUtc={nextRefreshUtc}
        timezone={timezone}
        feedHealth={feedHealth}
        tickEnabled={isActive}
      />
    </>
  )
}

function FeedView({ isActive, filters, setFilters, selectedCVE, setSelectedCVE,
                   digestOpen, setDigestOpen, digestCVEs, setDigestCVEs,
                   searchFocusTrigger, setSearchFocusTrigger, aboutOpen, setAboutOpen,
                   tutorialOpen,
                   timezone, lastUpdated, nextRefreshUtc,
                   onDigestRequest, watchlist, onWatchlistChange, onSelectCVE,
                   onOpenForgeCampaigns, feedHealth }) {

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

  return (
    <>
      <FeedRefreshStatus
        lastUpdated={lastUpdated}
        nextRefreshUtc={nextRefreshUtc}
        timezone={timezone}
        feedHealth={feedHealth}
        tickEnabled={isActive}
      />
      <div className="content-grid">
        <Suspense fallback={<TabLoading label="feed" />}>
        <CVEFeed
          filters={filters}
          onFiltersChange={handleFiltersChange}
          onSelectCVE={onSelectCVE}
          onGenerateDigest={handleGenerateDigest}
          onDigestRequest={onDigestRequest}
          onOpenForgeCampaigns={onOpenForgeCampaigns}
          searchFocusTrigger={searchFocusTrigger}
          timezone={timezone}
          overlayOpen={!!selectedCVE || digestOpen || aboutOpen || tutorialOpen}
          openedCveId={selectedCVE?.cve_id || null}
          watchlistVersion={watchlist?.version ?? 0}
          watchlist={watchlist}
          onWatchlistChange={onWatchlistChange}
        />
        </Suspense>
        <Sidebar filters={filters} onFiltersChange={handleFiltersChange} />
      </div>
    </>
  )
}

export default function App() {
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  // Primary nav is URL-owned (`tab=`). Forge still adds view/technique/pack.
  const [activeTab, setActiveTab] = useState(() => (
    typeof window !== 'undefined'
      ? resolveAppTab(new URLSearchParams(window.location.search))
      : 'brief'
  ))
  const selectAppTab = useCallback((tab) => {
    setActiveTab(tab)
    // Intentional tab change — Back should restore prior tab/Forge context.
    pushContext(setSearchParams, (prev) => buildAppTabSearchParams(prev, tab))
  }, [setActiveTab, setSearchParams])

  // Clear sticky focus/hover left inside a [hidden] app-tab-panel after ANY
  // activeTab change (selectAppTab, deep-links, back/forward, Forge pivots).
  // useEffect runs after paint, so [hidden] is already applied before blur.
  useEffect(() => {
    clearStalePointerState()
  }, [activeTab])

  const digestCVEsRef = useRef([])
  const generateDigestRef = useRef(null)
  const [filters, setFilters]                   = useState(DEFAULT_FILTERS)
  const [stats, setStats]                       = useState(null)
  const [selectedCVE, setSelectedCVE]           = useState(null)
  const [drawerLoading, setDrawerLoading]       = useState(false)
  const [drawerError, setDrawerError]           = useState(null)
  const drawerControllerRef = useRef(null)
  const [digestOpen, setDigestOpen]             = useState(false)
  const [digestCVEs, setDigestCVEs]             = useState([])
  const [searchFocusTrigger, setSearchFocusTrigger] = useState(0)
  const [aboutOpen, setAboutOpen]               = useState(false)
  const [paletteOpen, setPaletteOpen]           = useState(false)
  const [timezone, setTimezone]                 = useState(() => getTimezone())
  const [lastUpdated, setLastUpdated]           = useState(null)
  const [feedHealth, setFeedHealth]             = useState(null)
  const [nextRefreshUtc, setNextRefreshUtc]     = useState(null)
  const [iocPrefill, setIocPrefill]             = useState(null)
  const [iocSessionKey, setIocSessionKey]       = useState(0)
  const [atlasActorFilter, setAtlasActorFilter] = useState(null)
  const assetCtx = useAssetProfileOptional()
  const watchlist = useWatchlist()
  const { show: toast } = useToast()

  useEffect(() => {
    const onApiError = (e) => {
      const { message, requestId } = e.detail || {}
      toast({
        message,
        variant: 'error',
        actions: requestId
          ? [{ label: 'View application log', href: ingestLogUrl({ level: 'ERROR', requestId }) }]
          : [],
        requestId,
      })
    }
    window.addEventListener('briefr-api-error', onApiError)
    return () => window.removeEventListener('briefr-api-error', onApiError)
  }, [toast])

  const [statsError, setStatsError] = useState(null)
  const [statsErrorRequestId, setStatsErrorRequestId] = useState(null)
  const statsLoadSeqRef = useRef(0)

  const loadStats = useCallback(() => {
    const seq = ++statsLoadSeqRef.current
    const frameworks = getAiFrameworksForAlerts(assetCtx?.profile)
    fetchStats({ frameworks })
      .then(data => {
        if (seq !== statsLoadSeqRef.current) return
        setStats(data)
        setStatsError(null)
        setStatsErrorRequestId(null)
      })
      .catch(err => {
        if (seq !== statsLoadSeqRef.current) return
        setStatsError(err?.message || 'Failed to load stats.')
        setStatsErrorRequestId(err?.requestId || null)
        toast({
          message: err?.message || 'Failed to load stats.',
          variant: 'error',
          actions: err?.requestId
            ? [{ label: 'View application log', href: ingestLogUrl({ level: 'ERROR', requestId: err.requestId }) }]
            : [],
          requestId: err?.requestId,
        })
      })
  }, [assetCtx?.profile, toast])

  useEffect(() => {
    if (activeTab === 'feed') {
      setIocPrefill(null)
      setIocSessionKey(k => k + 1)
    }
  }, [activeTab])

  const loadHealth = useCallback(() => {
    fetchHealth(timezone)
      .then(h => {
        setFeedHealth(h)
        setLastUpdated(h.last_updated ?? null)
        setNextRefreshUtc(h.next_refresh_at_utc ?? null)
      })
      .catch(() => {})
  }, [timezone])

  useEffect(() => {
    drawerControllerRef.current = createCveDrawerController({
      fetchCVE,
      setSelectedCVE,
      setDrawerLoading,
      setDrawerError,
    })
  }, [])

  // Tracks the CVE id the drawer is showing so URL sync can close on Back
  // without re-opening from a stale selectedCVE state tick.
  const openDrawerCveIdRef = useRef(null)

  const handleOpenCVE = useCallback((cve) => {
    const id = cve?.cve_id ? String(cve.cve_id).trim().toUpperCase() : null
    if (id) openDrawerCveIdRef.current = id
    drawerControllerRef.current?.open(cve)
    // Sync open drawer to ?cve= so Back closes the drawer first.
    if (!id) return
    if (searchParams.get('cve')?.toUpperCase() === id) return
    pushContext(setSearchParams, (prev) => {
      const next = new URLSearchParams(prev)
      next.set('cve', id)
      return next
    })
  }, [searchParams, setSearchParams])

  const handleCloseCVE = useCallback(() => {
    openDrawerCveIdRef.current = null
    drawerControllerRef.current?.close()
    // Replace (not push) so Close does not leave a Back entry that re-opens.
    if (!searchParams.get('cve')) return
    replaceHygiene(setSearchParams, (prev) => {
      const next = new URLSearchParams(prev)
      next.delete('cve')
      return next
    })
  }, [searchParams, setSearchParams])

  const handleReplaceCVE = useCallback((full) => {
    drawerControllerRef.current?.replace(full)
  }, [])

  const handleRetryDrawer = useCallback(() => {
    drawerControllerRef.current?.retry()
  }, [])

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
    const existing = getSavedStack()
    if (existing) {
      setFilters((prev) => (prev.stack ? prev : { ...prev, stack: existing }))
    }
    function onStackLoaded(e) {
      const terms = e.detail?.stack_terms || ''
      setFilters((prev) => (prev.stack ? prev : { ...prev, stack: terms }))
    }
    window.addEventListener('briefr-stack-loaded', onStackLoaded)
    return () => window.removeEventListener('briefr-stack-loaded', onStackLoaded)
  }, [])

  useEffect(() => {
    loadHealth()
  }, [loadHealth])

  useVisibilityAwareInterval(loadHealth, 60000)

  // Keep timezone state in sync when Header or server prefs dispatch changes
  useEffect(() => {
    const onTz = (e) => setTimezone(e.detail)
    const onLoaded = (e) => setTimezone(e.detail?.timezone || getTimezone())
    window.addEventListener('briefr-timezone-change', onTz)
    window.addEventListener('briefr-preferences-loaded', onLoaded)
    return () => {
      window.removeEventListener('briefr-timezone-change', onTz)
      window.removeEventListener('briefr-preferences-loaded', onLoaded)
    }
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
    selectAppTab('feed')
    setFilters(prev => ({
      ...prev,
      ai_context_only: true,
      ai_profile_match: true,
      ai_profile: fw,
      kev_only: false,
      kev_overdue_only: false,
      poc_only: false,
      patch_only: false,
      severity: null,
      search: '',
      stack: '',
    }))
  }, [assetCtx?.profile, selectAppTab])

  const handleStatTileClick = useCallback((tile) => {
    selectAppTab('feed')
    const cleared = {
      severity: null,
      kev_only: false,
      kev_overdue_only: false,
      poc_only: false,
      patch_only: false,
      epss_min: null,
      search: '',
      stack: '',
      vendors: '',
      technique: '',
      published_on: '',
      watchlist_only: false,
      ai_context_only: false,
      ai_profile_match: false,
      ai_profile: '',
    }
    if (tile === 'critical') {
      setFilters(prev => ({ ...prev, ...cleared, severity: 'CRITICAL' }))
    } else if (tile === 'high') {
      setFilters(prev => ({ ...prev, ...cleared, severity: 'HIGH' }))
    } else if (tile === 'kev') {
      setFilters(prev => ({ ...prev, ...cleared, kev_only: true }))
    } else if (tile === 'patched') {
      setFilters(prev => ({ ...prev, ...cleared, patch_only: true }))
    }
  }, [selectAppTab])

  const openCveById = useCallback((cveId) => {
    handleOpenCVE({ cve_id: cveId })
  }, [handleOpenCVE])

  // URL ↔ drawer: keep ?cve= while open; clear on close; Back closes drawer first.
  useEffect(() => {
    const cveParam = searchParams.get('cve')
    if (!cveParam) {
      if (openDrawerCveIdRef.current) {
        openDrawerCveIdRef.current = null
        drawerControllerRef.current?.close()
      }
      return
    }
    if (!/^CVE-\d{4}-\d+$/i.test(cveParam.trim())) return
    const id = cveParam.trim().toUpperCase()
    if (openDrawerCveIdRef.current !== id) {
      openDrawerCveIdRef.current = id
      // Prefer staying on brief/feed if already there; else land on feed.
      setActiveTab((prev) => (prev === 'brief' || prev === 'feed' ? prev : 'feed'))
      drawerControllerRef.current?.open({ cve_id: id })
    }
    // Hygiene only: align tab= with the shell we landed on (no history entry).
    // Deep links like ?tab=forge&cve=… force feed above — URL must follow or
    // nav chrome and Back state disagree with the visible panel.
    const tab = searchParams.get('tab')
    if (tab === 'brief' || tab === 'feed') return
    replaceHygiene(setSearchParams, (prev) => {
      const next = buildAppTabSearchParams(prev, 'feed')
      next.set('cve', id)
      return next
    })
  }, [searchParams, setSearchParams, setActiveTab])

  const iocDeepLinkHandled = useRef(null)
  useEffect(() => {
    const iocParam = searchParams.get('ioc')
    if (!iocParam) {
      // Clear so the same ?ioc= value can deep-link again after navigate-away.
      iocDeepLinkHandled.current = null
      return
    }
    const value = iocParam.trim()
    if (!value || iocDeepLinkHandled.current === value) return
    iocDeepLinkHandled.current = value
    setActiveTab('ioc')
    setIocPrefill({
      value,
      indicators: [{ type: 'ip', value }],
      trigger: Date.now(),
    })
    // Strip one-shot ?ioc= without creating a Back entry.
    replaceHygiene(setSearchParams, (prev) => {
      const next = buildAppTabSearchParams(prev, 'ioc')
      next.delete('ioc')
      return next
    })
  }, [searchParams, setSearchParams, setActiveTab])

  // Keep React tab state + visible `tab=` in sync with the URL (back/forward,
  // legacy view=-only Forge links, first paint without tab=).
  useEffect(() => {
    if (searchParams.get('cve') || searchParams.get('ioc')) return
    const resolved = resolveAppTab(searchParams)
    setActiveTab((prev) => (prev === resolved ? prev : resolved))
    if (searchParams.get('tab') === resolved) return
    replaceHygiene(setSearchParams, (prev) => buildAppTabSearchParams(prev, resolved))
  }, [searchParams, setSearchParams])

  const investigationNav = useMemo(() => ({
    setActiveTab: selectAppTab,
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
    // Forge → CVE (and investigation pivots): one push so Back restores Forge.
    openCve: (cveId) => {
      if (!cveId) return
      const id = String(cveId).trim().toUpperCase()
      setActiveTab('brief')
      openDrawerCveIdRef.current = id
      drawerControllerRef.current?.open({ cve_id: id })
      pushContext(setSearchParams, (prev) => {
        const next = buildAppTabSearchParams(prev, 'brief')
        next.set('cve', id)
        return next
      })
    },
    // PM-4e: drawer MITRE pills → Forge ATT&CK navigator
    openForgeTechnique: (techniqueId) => {
      if (!techniqueId) return
      setActiveTab('forge')
      pushContext(setSearchParams, (prev) => {
        const next = buildAppTabSearchParams(prev, 'forge')
        next.set('view', 'coverage')
        next.set('technique', String(techniqueId))
        next.delete('pack')
        return next
      })
    },
  }), [setSearchParams, selectAppTab, setActiveTab])

  const openForgeCampaigns = useCallback(() => {
    setActiveTab('forge')
    pushContext(setSearchParams, (prev) => {
      const next = buildAppTabSearchParams(prev, 'forge')
      next.set('view', 'campaigns')
      next.delete('technique')
      next.delete('pack')
      return next
    })
  }, [setSearchParams, setActiveTab])

  const getPaletteCommands = useCallback((query) => {
    const q = query.trim()
    const ql = q.toLowerCase()
    const items = [
      { id: 'tab-brief', label: 'Go to BRIEF', hint: 'tab', keywords: ['brief'], run: () => selectAppTab('brief') },
      { id: 'tab-feed', label: 'Go to FEED', hint: 'tab', keywords: ['feed'], run: () => selectAppTab('feed') },
      { id: 'tab-ioc', label: 'Go to IOC LOOKUP', hint: 'tab', keywords: ['ioc', 'lookup'], run: () => selectAppTab('ioc') },
      { id: 'tab-atlas', label: 'Go to INCIDENTS & NEWS', hint: 'tab', keywords: ['incidents', 'news', 'atlas'], run: () => selectAppTab('atlas') },
      { id: 'tab-forge', label: 'Go to FORGE', hint: 'tab', keywords: ['forge'], run: () => selectAppTab('forge') },
      {
        id: 'refresh-stats',
        label: 'Refresh dashboard stats',
        hint: 'action',
        keywords: ['refresh', 'reload', 'stats'],
        run: () => {
          loadStats()
          loadHealth()
        },
      },
    ]

    const cve = q.toUpperCase()
    if (/^CVE-\d{4}-\d+$/.test(cve)) {
      items.unshift({
        id: `open-${cve}`,
        label: `Open ${cve}`,
        hint: 'cve',
        run: () => {
          selectAppTab('feed')
          openCveById(cve)
        },
      })
    }

    const looksLikeIoc = q.length >= 3
      && !/^CVE-/i.test(q)
      && (
        /^(\d{1,3}\.){3}\d{1,3}$/.test(q)
        || /^[0-9a-fA-F]{32}$|^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$/.test(q)
        || (q.includes('.') && !q.includes(' '))
      )
    if (looksLikeIoc) {
      const display = q.length > 40 ? `${q.slice(0, 40)}…` : q
      items.unshift({
        id: 'ioc-lookup',
        label: `Review indicators: ${display}`,
        hint: 'ioc',
        run: () => {
          selectAppTab('ioc')
          investigationNav.setIocPrefill(q)
        },
      })
    }

    if (!ql) return items
    return items.filter(cmd =>
      cmd.label.toLowerCase().includes(ql)
      || cmd.keywords?.some(k => k.includes(ql) || ql.includes(k))
    )
  }, [investigationNav, loadHealth, loadStats, openCveById, selectAppTab])

  useEffect(() => {
    function onPaletteKey(e) {
      if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== 'k') return
      e.preventDefault()
      setPaletteOpen(open => !open)
    }
    document.addEventListener('keydown', onPaletteKey)
    return () => document.removeEventListener('keydown', onPaletteKey)
  }, [])

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
        if (selectedCVE)  { handleCloseCVE(); return }
        return
      }
      if (shouldIgnoreGlobalShortcut(e)) return

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
  }, [aboutOpen, selectedCVE, digestOpen, handleGenerateDigest, activeTab, handleCloseCVE])

  const showFeedShortcuts =
    location.pathname !== '/privacy' &&
    location.pathname !== '/terms' &&
    activeTab === 'feed'

  const handleSelectCVE = handleOpenCVE

  const handleWatchlistChange = useCallback(async (cveId, action) => {
    if (action !== 'pin') return
    try {
      const current =
        watchlist.getState(cveId) ||
        (selectedCVE?.cve_id === cveId ? selectedCVE.watchlist_state : null)
      await watchlist.togglePin(cveId, current)
      if (selectedCVE?.cve_id === cveId) {
        const full = await fetchCVE(cveId)
        handleReplaceCVE(full)
      }
    } catch {
      // Controls are best-effort; feed refetch follows version bump.
    }
  }, [watchlist, selectedCVE, handleReplaceCVE])

  return (
    <InvestigationProvider navigation={investigationNav}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/admin/*" element={
          <RequireAuth>
            <RequireAdmin>
              <Suspense fallback={<TabLoading label="admin" />}>
                <AdminPage />
              </Suspense>
            </RequireAdmin>
          </RequireAuth>
        } />
        <Route path="/security-architecture/*" element={
          <RequireAuth>
            <SecurityArchitectureRedirect />
          </RequireAuth>
        } />
        <Route path="/wallboard" element={
          <ToolErrorBoundary label="Wallboard">
            <Suspense fallback={<TabLoading label="wallboard" />}>
              <WallboardPage />
            </Suspense>
          </ToolErrorBoundary>
        } />
        <Route
          path="*"
          element={(
            <RequireAuth>
            <AppLayout
              activeTab={activeTab}
              setActiveTab={selectAppTab}
              showFeedShortcuts={showFeedShortcuts}
              onAboutOpen={() => setAboutOpen(true)}
              onTimezoneChange={setTimezone}
              iocPrefill={iocPrefill}
              iocSessionKey={iocSessionKey}
              atlasActorFilter={atlasActorFilter}
              onClearAtlasFilter={() => setAtlasActorFilter(null)}
              stats={stats}
              statsError={statsError}
              statsErrorRequestId={statsErrorRequestId}
              onRetryStats={loadStats}
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
              feedHealth={feedHealth}
              onDigestRequest={registerDigestHandler}
              openCveById={openCveById}
              onOpenForgeCampaigns={openForgeCampaigns}
              showAiAlerts={showAiAlerts}
              onAiAlertsClick={handleAiAlertsClick}
              onStatTileClick={handleStatTileClick}
              onSelectCVE={handleSelectCVE}
              onCloseCVE={handleCloseCVE}
              onCveReplace={handleReplaceCVE}
              drawerLoading={drawerLoading}
              drawerError={drawerError}
              onRetryDrawer={handleRetryDrawer}
              watchlist={watchlist}
              onWatchlistChange={handleWatchlistChange}
            />
            </RequireAuth>
          )}
        />
      </Routes>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        getCommands={getPaletteCommands}
      />
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
  statsError,
  statsErrorRequestId,
  onRetryStats,
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
  feedHealth,
  onDigestRequest,
  openCveById,
  onOpenForgeCampaigns,
  showAiAlerts,
  onAiAlertsClick,
  onStatTileClick,
  onSelectCVE,
  onCloseCVE,
  onCveReplace,
  drawerLoading,
  drawerError,
  onRetryDrawer,
  watchlist,
  onWatchlistChange,
}) {
  const { showPanel, panelExpanded } = useInvestigation()
  const [mountedTabs, setMountedTabs] = useState({ brief: true })
  const [drawerMounted, setDrawerMounted] = useState(false)
  const [invMounted, setInvMounted] = useState(false)
  const [tutorialOpen, setTutorialOpen] = useState(false)

  useEffect(() => {
    setMountedTabs(prev => (prev[activeTab] ? prev : { ...prev, [activeTab]: true }))
  }, [activeTab])

  // AppLayout only mounts once the user is past login/admin/wallboard routes
  // (see the "*" Route in App()), so this is the right place for the
  // first-visit check — no route-path filtering needed here.
  useEffect(() => {
    if (!hasTutorialSeen()) setTutorialOpen(true)
  }, [])

  useEffect(() => {
    if (selectedCVE) setDrawerMounted(true)
  }, [selectedCVE])

  useEffect(() => {
    if (showPanel) setInvMounted(true)
  }, [showPanel])

  const layoutClass = [
    'app',
    'app-layout',
    showPanel ? 'has-investigation' : '',
    showPanel && panelExpanded ? 'investigation-expanded' : '',
  ].filter(Boolean).join(' ')

  return (
    <div className={layoutClass}>
      {invMounted && (
        <Suspense fallback={null}>
          <InvestigationPanel />
        </Suspense>
      )}
      <div className="app-shell">
        <Header
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onAboutOpen={onAboutOpen}
          onTutorialOpen={() => setTutorialOpen(true)}
          onLogoClick={() => setActiveTab('brief')}
          onTimezoneChange={onTimezoneChange}
          showShortcuts={showFeedShortcuts}
          feedHealth={feedHealth}
        />

        <div className="app-main">
          <div className="app-tab-panel" hidden={activeTab !== 'brief'} aria-hidden={activeTab !== 'brief'}>
            <ToolErrorBoundary label="Brief">
              <BriefView
                isActive={activeTab === 'brief'}
                stats={stats}
                statsError={statsError}
                statsErrorRequestId={statsErrorRequestId}
                onRetryStats={onRetryStats}
                filters={filters}
                setFilters={setFilters}
                timezone={timezone}
                lastUpdated={lastUpdated}
                nextRefreshUtc={nextRefreshUtc}
                showAiAlerts={showAiAlerts}
                onAiAlertsClick={onAiAlertsClick}
                onStatTileClick={onStatTileClick}
                onOpenFullFeed={() => setActiveTab('feed')}
                onSelectCVE={onSelectCVE}
                feedHealth={feedHealth}
              />
            </ToolErrorBoundary>
          </div>
          <div className="app-tab-panel" hidden={activeTab !== 'feed'} aria-hidden={activeTab !== 'feed'}>
            {mountedTabs.feed && (
              <ToolErrorBoundary label="Feed">
                <FeedView
                isActive={activeTab === 'feed'}
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
                tutorialOpen={tutorialOpen}
                timezone={timezone}
                lastUpdated={lastUpdated}
                nextRefreshUtc={nextRefreshUtc}
                onDigestRequest={onDigestRequest}
                onSelectCVE={onSelectCVE}
                onOpenForgeCampaigns={onOpenForgeCampaigns}
                watchlist={watchlist}
                onWatchlistChange={onWatchlistChange}
                feedHealth={feedHealth}
              />
              </ToolErrorBoundary>
            )}
          </div>
          <div className="app-tab-panel" hidden={activeTab !== 'ioc'} aria-hidden={activeTab !== 'ioc'}>
            {mountedTabs.ioc && (
              <Suspense fallback={<TabLoading label="IOC Lookup" />}>
                <ToolErrorBoundary label="IOC Lookup">
                  <IOCLookup key={iocSessionKey} prefill={iocPrefill} />
                </ToolErrorBoundary>
              </Suspense>
            )}
          </div>
          <div className="app-tab-panel" hidden={activeTab !== 'atlas'} aria-hidden={activeTab !== 'atlas'}>
            {mountedTabs.atlas && (
              <Suspense fallback={<TabLoading label="ATLAS" />}>
                <ToolErrorBoundary label="ATLAS">
                  <CaseStudies
                    initialSearch={atlasActorFilter || ''}
                    onClearFilter={onClearAtlasFilter}
                    onOpenCve={openCveById}
                  />
                </ToolErrorBoundary>
              </Suspense>
            )}
          </div>
          <div className="app-tab-panel" hidden={activeTab !== 'forge'} aria-hidden={activeTab !== 'forge'}>
            {mountedTabs.forge && (
              <Suspense fallback={<TabLoading label="Forge" />}>
                <ToolErrorBoundary label="Forge">
                  <Forge />
                </ToolErrorBoundary>
              </Suspense>
            )}
          </div>
        </div>

            {activeTab !== 'feed' && (
              <footer className="app-footer" role="contentinfo">
                <div className="footer-left">
                  <span>BRIEFR</span> // CVE intelligence platform
                  <span className="footer-copyright mono">
                    &copy; 2026 BRIEFR &middot; Apache-2.0
                  </span>
                </div>
                <nav className="footer-legal" aria-label="Legal links">
                  <button type="button" className="footer-legal-link mono" onClick={onAboutOpen}>About</button>
                  <span className="footer-legal-sep" aria-hidden="true">&middot;</span>
                  <Link to="/privacy" className="footer-legal-link mono">Privacy Policy</Link>
                  <span className="footer-legal-sep" aria-hidden="true">&middot;</span>
                  <Link to="/terms" className="footer-legal-link mono">Terms of Use</Link>
                </nav>
                <div className="footer-right" style={{ fontSize: '0.6875rem', color: 'var(--text3)' }}>
                  All times UTC &mdash; not a substitute for professional security advice
                </div>
              </footer>
            )}


            <ToolErrorBoundary key={selectedCVE?.cve_id || 'empty'} label="CVE detail" onReset={onCloseCVE}>
              {drawerMounted && (
                <Suspense fallback={null}>
                  <DetailDrawer
                    cve={selectedCVE}
                    loading={drawerLoading}
                    error={drawerError}
                    onRetry={onRetryDrawer}
                    onClose={onCloseCVE}
                    onCveReplace={onCveReplace}
                    watchlistState={
                      selectedCVE
                        ? (watchlist?.getState(selectedCVE.cve_id) || selectedCVE.watchlist_state)
                        : null
                    }
                    onWatchlistChange={onWatchlistChange}
                  />
                </Suspense>
              )}
            </ToolErrorBoundary>

            {digestOpen && (
              <ToolErrorBoundary label="Digest" onReset={() => setDigestOpen(false)}>
                <DigestModal cves={digestCVEs} filters={filters} onClose={() => setDigestOpen(false)} />
              </ToolErrorBoundary>
            )}

            {aboutOpen && (
              <ToolErrorBoundary label="About" onReset={() => setAboutOpen(false)}>
                <AboutModal onClose={() => setAboutOpen(false)} />
              </ToolErrorBoundary>
            )}

            {tutorialOpen && (
              <ToolErrorBoundary label="Tutorial" onReset={() => setTutorialOpen(false)}>
                <TutorialOverlay
                  onClose={() => { setTutorialOpen(false); markTutorialSeen() }}
                  activeTab={activeTab}
                  onTabChange={setActiveTab}
                />
              </ToolErrorBoundary>
            )}
      </div>
    </div>
  )
}
