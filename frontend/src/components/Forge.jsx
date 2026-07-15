import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchForgeCoverage, generateHuntPack } from '../api.js'
import { notifyApiError } from './Toast.jsx'
import { useAssetProfileOptional } from '../context/AssetProfileContext.jsx'
import { profileToMatchAssets } from '../utils/assetProfileIo.js'
import { Checkbox, Tabs, TabsList, TabsTrigger } from './ui/index.js'
import { StatusChip, ForgeStatusLegend } from './forge/shared.jsx'
import CoverageView from './forge/CoverageView.jsx'
import ScenariosView from './forge/ScenariosView.jsx'
import CampaignsView from './forge/CampaignsView.jsx'
import BacklogView from './forge/BacklogView.jsx'
import LibraryView from './forge/LibraryView.jsx'
import HuntPackRail from './forge/HuntPackRail.jsx'
import { ingestLogUrl } from '../utils/adminLinks.js'
import './Forge.css'

const VALID_VIEWS = new Set(['coverage', 'scenarios', 'campaigns', 'backlog', 'library'])

const NAV_ITEMS = [
  { id: 'coverage', label: 'Coverage map' },
  { id: 'scenarios', label: 'Threat scenarios' },
  { id: 'campaigns', label: 'Campaigns' },
  { id: 'backlog', label: 'Backlog' },
  { id: 'library', label: 'Library' },
]

/**
 * Forge shell (FR-2, forge-redesign.md §5): three-panel layout — left nav,
 * center workspace (one view at a time), persistent Hunt Pack rail. All
 * selection state lives here and round-trips through the URL
 * (?view=&technique=&pack=) so refresh and deep links never lose context —
 * this is the fix for P1 (view state) and P2 (rail vanishing per-view).
 */
export default function Forge() {
  const [searchParams, setSearchParams] = useSearchParams()

  const initialView = VALID_VIEWS.has(searchParams.get('view')) ? searchParams.get('view') : 'coverage'
  const [viewMode, setViewModeState] = useState(initialView)
  const [selectedTechnique, setSelectedTechniqueState] = useState(searchParams.get('technique') || null)
  const [selectedPackId, setSelectedPackIdState] = useState(() => {
    const raw = searchParams.get('pack')
    return raw ? Number(raw) || null : null
  })
  const [railOpen, setRailOpen] = useState(() => Boolean(searchParams.get('technique')))

  const [coverage, setCoverage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)
  const [stackOnly, setStackOnly] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [generatingFromScenario, setGeneratingFromScenario] = useState(null)
  const assetCtx = useAssetProfileOptional()

  // Browser back/forward (or an external link) changes searchParams outside
  // our own writeUrl calls — mirror it back into state so the URL stays the
  // single source of truth for view + selection.
  useEffect(() => {
    const view = VALID_VIEWS.has(searchParams.get('view')) ? searchParams.get('view') : 'coverage'
    setViewModeState(view)
    setSelectedTechniqueState(searchParams.get('technique') || null)
    const rawPack = searchParams.get('pack')
    setSelectedPackIdState(rawPack ? Number(rawPack) || null : null)
  }, [searchParams])

  const writeUrl = useCallback((patch) => {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(patch)) {
      if (value === null || value === undefined || value === '') next.delete(key)
      else next.set(key, String(value))
    }
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const setViewMode = useCallback((view) => {
    setViewModeState(view)
    writeUrl({ view })
    setRailOpen(false)
  }, [writeUrl])

  const setSelectedTechnique = useCallback((techniqueId) => {
    setSelectedTechniqueState(techniqueId)
    setSelectedPackIdState(null)
    writeUrl({ technique: techniqueId, pack: null })
    if (techniqueId) setRailOpen(true)
  }, [writeUrl])

  const openPack = useCallback((techniqueId, packId) => {
    setSelectedTechniqueState(techniqueId)
    setSelectedPackIdState(packId)
    writeUrl({ technique: techniqueId, pack: packId })
    setRailOpen(true)
  }, [writeUrl])

  const closeRail = useCallback(() => setRailOpen(false), [])

  useEffect(() => {
    if (viewMode === 'library') return undefined
    function onKey(e) {
      if (e.key === 'Escape') closeRail()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [viewMode, closeRail])

  const profileStack = useMemo(() => {
    if (!assetCtx?.isLoaded || !assetCtx?.profile) return ''
    const products = profileToMatchAssets(assetCtx.profile)
      .map(a => a.product)
      .filter(Boolean)
    return [...new Set(products)].join(', ')
  }, [assetCtx?.isLoaded, assetCtx?.profile])

  useEffect(() => {
    if (!profileStack) setStackOnly(false)
  }, [profileStack])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setErrorRequestId(null)
    fetchForgeCoverage(stackOnly ? profileStack : '')
      .then(data => { if (!cancelled) setCoverage(data) })
      .catch(err => {
        if (!cancelled) {
          setError(err.message || 'Failed to load coverage map')
          setErrorRequestId(err?.requestId || null)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [stackOnly, profileStack, reloadKey])

  const handleRetryCoverage = useCallback(() => setReloadKey(k => k + 1), [])

  // A saved pack flips the technique to "yours" — refetch keeps the map honest.
  const handlePackSaved = useCallback(() => {
    setReloadKey(k => k + 1)
  }, [])

  const handleScenarioGenerate = useCallback((cveId, techniqueId) => {
    setGeneratingFromScenario(cveId)
    setSelectedTechnique(techniqueId)
    generateHuntPack(cveId, techniqueId)
      .then(() => handlePackSaved())
      .catch(err => notifyApiError(err))
      .finally(() => setGeneratingFromScenario(null))
  }, [handlePackSaved, setSelectedTechnique])

  const handlePackDeleted = useCallback((pack) => {
    if (selectedPackId === pack.id) {
      setSelectedTechniqueState(null)
      setSelectedPackIdState(null)
      writeUrl({ technique: null, pack: null })
    }
    setReloadKey(k => k + 1)
  }, [selectedPackId, writeUrl])

  const counts = coverage?.meta?.counts

  return (
    <div className="forge" role="region" aria-label="Forge detection engineering">
      <header className="fg-hero">
        <p className="fg-hero-kicker mono">DETECTION ENGINEERING</p>
        <h1 className="fg-hero-title">Forge</h1>
        <p className="fg-hero-sub">
          See which ATT&amp;CK techniques your feed CVEs map to, review environment threat scenarios
          for your stack, find community detection rules, and export Sigma and SIEM hunt templates per CVE.
          Rules are starting points — validate before production.
        </p>
      </header>

      <div className="fg-shell">
        <nav className="fg-nav" aria-label="Forge views">
          <Tabs value={viewMode} onValueChange={setViewMode} className="fg-nav-tabs-wrap">
            <TabsList className="fg-nav-tabs mono" aria-label="Forge view">
              {NAV_ITEMS.map(item => (
                <TabsTrigger
                  key={item.id}
                  value={item.id}
                  className="fg-nav-btn"
                >
                  {item.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          {counts && (
            <div className="fg-counts fg-counts-nav" role="status" aria-label="Coverage summary">
              <span className="fg-count mono">
                <StatusChip status="gap" /> {counts.gap}
              </span>
              <span className="fg-count mono">
                <StatusChip status="community" /> {counts.community}
              </span>
              <span className="fg-count mono">
                <StatusChip status="yours" /> {counts.yours}
              </span>
            </div>
          )}
          {profileStack && (
            <Checkbox
              id="forge-stack-only-nav"
              checked={stackOnly}
              onCheckedChange={setStackOnly}
              label={`MY STACK ONLY (${profileStack})`}
              className="fg-stack-toggle fg-stack-toggle-nav mono"
            />
          )}
          <details className="severity-legend-feed forge-status-legend-details">
            <summary className="severity-legend-feed-summary mono">STATUS LEGEND</summary>
            <ForgeStatusLegend />
          </details>
        </nav>

        <div className="fg-workspace">
          {error && (
            <div className="fg-error-block">
              <p className="fg-error mono">
                // {error}
                {errorRequestId && (
                  <>
                    {' '}
                    (<a href={ingestLogUrl({ level: 'ERROR', requestId: errorRequestId })}>
                      ref: {errorRequestId}
                    </a>)
                  </>
                )}
              </p>
              <button type="button" className="fg-error-retry-btn mono" onClick={handleRetryCoverage}>
                Retry
              </button>
            </div>
          )}

          {viewMode === 'coverage' && (
            <CoverageView
              coverage={coverage}
              loading={loading}
              stackOnly={stackOnly}
              selectedTechnique={selectedTechnique}
              onSelectTechnique={setSelectedTechnique}
            />
          )}
          {viewMode === 'scenarios' && (
            <ScenariosView
              profileStack={profileStack}
              selectedTechnique={selectedTechnique}
              onSelectTechnique={setSelectedTechnique}
              onGeneratePack={handleScenarioGenerate}
              generatingCve={generatingFromScenario}
            />
          )}
          {viewMode === 'campaigns' && (
            <CampaignsView profileStack={profileStack} />
          )}
          {viewMode === 'backlog' && (
            <BacklogView
              profileStack={profileStack}
              onGeneratePack={handleScenarioGenerate}
              generatingCve={generatingFromScenario}
              onDismissed={handlePackSaved}
            />
          )}
          {viewMode === 'library' && (
            <LibraryView
              selectedPackId={selectedPackId}
              onOpenPack={openPack}
              onPackDeleted={handlePackDeleted}
            />
          )}
        </div>

        {railOpen && (
          <button
            type="button"
            className="fg-rail-backdrop"
            aria-label="Close hunt pack rail"
            onClick={closeRail}
          />
        )}
        <aside className={`fg-detail${railOpen ? ' fg-detail-open' : ''}`} aria-label="Hunt pack detail">
          <div className="fg-detail-head">
            <h2 className="fg-section-label mono">HUNT PACK</h2>
            <button type="button" className="fg-detail-close mono" onClick={closeRail} aria-label="Close hunt pack rail">
              ✕
            </button>
          </div>
          <HuntPackRail
            techniqueId={selectedTechnique}
            onPackSaved={handlePackSaved}
          />
        </aside>
      </div>
    </div>
  )
}
