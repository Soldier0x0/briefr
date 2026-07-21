import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchForgeCoverage, generateHuntPack } from '../api.js'
import { notifyApiError } from './Toast.jsx'
import { useAssetProfileOptional } from '../context/AssetProfileContext.jsx'
import { profileToMatchAssets } from '../utils/assetProfileIo.js'
import { Checkbox, Tabs, TabsList, TabsTrigger } from './ui/index.js'
import CoverageView from './forge/CoverageView.jsx'
import ScenariosView from './forge/ScenariosView.jsx'
import CampaignsView from './forge/CampaignsView.jsx'
import BacklogView from './forge/BacklogView.jsx'
import LibraryView from './forge/LibraryView.jsx'
import HuntPackRail from './forge/HuntPackRail.jsx'
import { ingestLogUrl } from '../utils/adminLinks.js'
import { forgeHeroSub, hasPersonalizationContext } from '../utils/personalizationCopy.js'
import './Forge.css'

const VALID_VIEWS = new Set(['coverage', 'scenarios', 'campaigns', 'backlog', 'library'])

const NAV_ITEMS = [
  { id: 'coverage', label: 'ATT&CK navigator' },
  { id: 'scenarios', label: 'Threat scenarios' },
  { id: 'campaigns', label: 'Campaigns' },
  { id: 'backlog', label: 'Backlog' },
  { id: 'library', label: 'Library' },
]

/**
 * Forge shell: top view tabs + workspace. Hunt pack docks under the ATT&CK
 * navigator only (coverage). Technique click toggles selection. Selection
 * clears when leaving coverage so the panel does not follow other views.
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
  const [railOpen, setRailOpen] = useState(
    () => initialView === 'coverage' && Boolean(searchParams.get('technique')),
  )

  const [coverage, setCoverage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)
  const [stackOnly, setStackOnly] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [generatingFromScenario, setGeneratingFromScenario] = useState(null)
  const assetCtx = useAssetProfileOptional()

  const writeUrl = useCallback((patch) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      for (const [key, value] of Object.entries(patch)) {
        if (value === null || value === undefined || value === '') next.delete(key)
        else next.set(key, String(value))
      }
      return next
    }, { replace: true })
  }, [setSearchParams])

  const clearTechniqueSelection = useCallback(() => {
    setSelectedTechniqueState(null)
    setSelectedPackIdState(null)
    setRailOpen(false)
    writeUrl({ technique: null, pack: null })
  }, [writeUrl])

  // Browser back/forward (or an external link) changes searchParams outside
  // our own writeUrl calls — mirror it back into state so the URL stays the
  // single source of truth for view + selection.
  useEffect(() => {
    const view = VALID_VIEWS.has(searchParams.get('view')) ? searchParams.get('view') : 'coverage'
    setViewModeState(view)
    const techniqueId = searchParams.get('technique') || null
    const rawPack = searchParams.get('pack')
    const packId = rawPack ? Number(rawPack) || null : null

    // Hunt pack / technique selection is coverage-scoped. Drop URL state when
    // deep-linking into another view with a stale technique= param.
    if (view !== 'coverage') {
      setSelectedTechniqueState(null)
      setSelectedPackIdState(view === 'library' ? packId : null)
      setRailOpen(false)
      if (techniqueId || (view !== 'library' && packId)) {
        const next = new URLSearchParams(searchParams)
        next.delete('technique')
        if (view !== 'library') next.delete('pack')
        setSearchParams(next, { replace: true })
      }
      return
    }

    setSelectedTechniqueState(techniqueId)
    setSelectedPackIdState(packId)
    setRailOpen(Boolean(techniqueId))
  }, [searchParams, setSearchParams])

  const setViewMode = useCallback((view) => {
    setViewModeState(view)
    setSelectedTechniqueState(null)
    setSelectedPackIdState(null)
    setRailOpen(false)
    writeUrl({ view, technique: null, pack: null })
  }, [writeUrl])

  const setSelectedTechnique = useCallback((techniqueId) => {
    if (techniqueId && techniqueId === selectedTechnique && viewMode === 'coverage') {
      clearTechniqueSelection()
      return
    }
    if (!techniqueId) {
      clearTechniqueSelection()
      return
    }
    // Technique selection belongs on the ATT&CK navigator (opens hunt pack there).
    setViewModeState('coverage')
    setSelectedTechniqueState(techniqueId)
    setSelectedPackIdState(null)
    writeUrl({ view: 'coverage', technique: techniqueId, pack: null })
    setRailOpen(true)
  }, [writeUrl, selectedTechnique, clearTechniqueSelection, viewMode])

  const openPack = useCallback((techniqueId, packId) => {
    // Library can highlight a pack in-context; jump to coverage + hunt pack
    // only when a technique is supplied.
    if (techniqueId) {
      setViewModeState('coverage')
      setSelectedTechniqueState(techniqueId)
      setSelectedPackIdState(packId)
      writeUrl({ view: 'coverage', technique: techniqueId, pack: packId })
      setRailOpen(true)
      return
    }
    setSelectedTechniqueState(null)
    setSelectedPackIdState(packId)
    writeUrl({ technique: null, pack: packId })
    setRailOpen(false)
  }, [writeUrl])

  const closeRail = useCallback(() => {
    clearTechniqueSelection()
  }, [clearTechniqueSelection])

  useEffect(() => {
    if (viewMode !== 'coverage') return undefined
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

  const heroPersonalized = hasPersonalizationContext({ stackTerms: profileStack })

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

  const handlePackSaved = useCallback(() => {
    setReloadKey(k => k + 1)
  }, [])

  const handleScenarioGenerate = useCallback((cveId, techniqueId) => {
    setGeneratingFromScenario(cveId)
    setViewModeState('coverage')
    setSelectedTechniqueState(techniqueId)
    setSelectedPackIdState(null)
    writeUrl({ view: 'coverage', technique: techniqueId, pack: null })
    setRailOpen(Boolean(techniqueId))
    generateHuntPack(cveId, techniqueId)
      .then(() => handlePackSaved())
      .catch(err => notifyApiError(err))
      .finally(() => setGeneratingFromScenario(null))
  }, [handlePackSaved, writeUrl])

  const handlePackDeleted = useCallback((pack) => {
    if (selectedPackId === pack.id) {
      clearTechniqueSelection()
    }
    setReloadKey(k => k + 1)
  }, [selectedPackId, clearTechniqueSelection])

  const showHuntPack = viewMode === 'coverage' && railOpen && Boolean(selectedTechnique)

  return (
    <div className="forge" role="region" aria-label="Forge detection engineering">
      <header className="fg-hero">
        <p className="fg-hero-kicker mono">DETECTION ENGINEERING</p>
        <h1 className="fg-hero-title">Forge</h1>
        <p className="fg-hero-sub">
          {forgeHeroSub({ personalized: heroPersonalized })}
        </p>
      </header>

      <div className={`fg-shell${showHuntPack ? ' fg-shell--detail-open' : ''}`}>
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
          {profileStack && (
            <Checkbox
              id="forge-stack-only-nav"
              checked={stackOnly}
              onCheckedChange={setStackOnly}
              label={`MY STACK ONLY (${profileStack})`}
              className="fg-stack-toggle fg-stack-toggle-nav mono"
            />
          )}
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

        {showHuntPack && (
          <button
            type="button"
            className="fg-rail-backdrop"
            aria-label="Close hunt pack panel"
            onClick={closeRail}
          />
        )}
        <aside
          className={`fg-detail${showHuntPack ? ' fg-detail-open' : ''}`}
          aria-label="Hunt pack detail"
          hidden={!showHuntPack}
        >
          <div className="fg-detail-head">
            <h2 className="fg-section-label mono">HUNT PACK</h2>
            <button type="button" className="fg-detail-close mono" onClick={closeRail} aria-label="Close hunt pack panel">
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
