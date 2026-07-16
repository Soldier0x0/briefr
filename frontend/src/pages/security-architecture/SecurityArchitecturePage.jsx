import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchSecurityArchitectureManifest } from '../../api.js'
import { notifyApiError } from '../../components/Toast.jsx'
import { humanizeSectionId, DEFAULT_SECTION } from './constants.js'
import OverviewSection from './sections/OverviewSection.jsx'
import GenericSection from './sections/GenericSection.jsx'
import MitreSection from './sections/MitreSection.jsx'
import ThreatScenariosSection from './sections/ThreatScenariosSection.jsx'
import ArchitectureGraphSection from './sections/ArchitectureGraphSection.jsx'
import TrustBoundariesSection from './sections/TrustBoundariesSection.jsx'
import AttackSurfaceSection from './sections/AttackSurfaceSection.jsx'
import RiskRegisterSection from './sections/RiskRegisterSection.jsx'
import DecisionsSection from './sections/DecisionsSection.jsx'
import AbuseCasesSection from './sections/AbuseCasesSection.jsx'
import ReviewHistorySection from './sections/ReviewHistorySection.jsx'
import StaleRecordsSection from './sections/StaleRecordsSection.jsx'
import ContextRail from './ContextRail.jsx'
import GlobalSearch from './GlobalSearch.jsx'
import './SecurityArchitecturePage.css'

/**
 * Security Architecture shell (TM-2, threat-modeling-security-architecture.md
 * §3.1 + §8): three-panel layout mirroring Forge (FR-2) and Admin --
 * left nav / center workspace / persistent context rail, all selection
 * state round-tripping through the URL (?section=&status=&severity=&type=)
 * so refresh and deep links never lose context (same fix class as FR-2 P1).
 *
 * The nav is manifest-driven (spec §2.2, §8): it renders whatever
 * `GET /api/security-architecture/manifest` lists in `sections[]`, not a
 * hardcoded list. TM-1's manifest currently lists 9 sections (overview +
 * 8 data sections) -- narrower than spec §2.2's 18-row aspirational catalog
 * (MITRE, STRIDE, OWASP, ... are TM-3+/TM-6+ and don't exist in the corpus
 * yet). That's an intentional, documented divergence: the nav shows what's
 * real, not a "coming soon" placeholder list (spec §2.2's own rule).
 *
 * Context rail starts and stays in an empty state in TM-2 -- sections that
 * populate it (component detail, technique detail, risk detail, ...) are
 * TM-3+ scope (spec §8 TM-2: "context rail empty state").
 */
export default function SecurityArchitecturePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [manifest, setManifest] = useState(null)
  const [manifestError, setManifestError] = useState(null)
  const navRefs = useRef({})

  const section = searchParams.get('section') || DEFAULT_SECTION
  const filters = useMemo(() => ({
    type: searchParams.get('type') || '',
    status: searchParams.get('status') || '',
    severity: searchParams.get('severity') || '',
    origin: searchParams.get('origin') || '',
  }), [searchParams])
  // Graph node selection round-trips through the URL (?node=) like every
  // other selection in this module -- "selection is never lost by
  // navigation inside the module" (playbook §3 smoothness budget).
  const selectedNodeId = searchParams.get('node') || ''

  useEffect(() => {
    let cancelled = false
    fetchSecurityArchitectureManifest()
      .then(res => { if (!cancelled) setManifest(res) })
      .catch(err => {
        if (!cancelled) {
          setManifestError(err)
          notifyApiError(err)
        }
      })
    return () => { cancelled = true }
  }, [])

  const goToSection = useCallback((nextSection, nextFilters = {}) => {
    const next = new URLSearchParams()
    next.set('section', nextSection)
    for (const [key, value] of Object.entries(nextFilters)) {
      if (value !== undefined && value !== null && value !== '') next.set(key, String(value))
    }
    setSearchParams(next)
  }, [setSearchParams])

  const setFilters = useCallback((nextFilters) => {
    goToSection(section, nextFilters)
  }, [section, goToSection])

  const selectNode = useCallback((nodeId) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.set('node', nodeId)
      return next
    })
  }, [setSearchParams])

  const clearSelection = useCallback(() => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.delete('node')
      return next
    })
  }, [setSearchParams])

  const navSections = manifest?.sections || (manifestError ? [] : [DEFAULT_SECTION])

  // Roving-tabindex arrow-key navigation between nav sections (spec §9.10:
  // "Tab through nav, Enter to select" -- arrow keys are the standard
  // complement for a vertical tablist, matching Forge's role="tablist" nav).
  const handleNavKeyDown = useCallback((e, index) => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
    e.preventDefault()
    const delta = e.key === 'ArrowDown' ? 1 : -1
    const nextIndex = (index + delta + navSections.length) % navSections.length
    const nextId = navSections[nextIndex]
    navRefs.current[nextId]?.focus()
    goToSection(nextId)
  }, [navSections, goToSection])

  return (
    <div className="sa-root">
      <header className="sa-topbar">
        <Link to="/" className="sa-brand-link mono" title="Back to BRIEFR">BRIEFR</Link>
        <span className="sa-topbar-sep" aria-hidden="true">//</span>
        <span className="sa-topbar-title mono">SECURITY ARCHITECTURE</span>
        <GlobalSearch onOpenSection={(id) => goToSection(id)} />
      </header>

      <div className={`sa-shell${section === 'system_architecture' ? ' sa-shell--graph' : ''}`}>
        <nav className="sa-nav" aria-label="Security architecture sections">
          <div className="sa-nav-list" role="tablist" aria-label="Section" aria-orientation="vertical">
            {navSections.map((id, i) => (
              <button
                key={id}
                ref={el => { navRefs.current[id] = el }}
                type="button"
                role="tab"
                tabIndex={section === id ? 0 : -1}
                aria-selected={section === id}
                aria-current={section === id ? 'page' : undefined}
                className={`sa-nav-btn${section === id ? ' active' : ''}`}
                onClick={() => goToSection(id)}
                onKeyDown={(e) => handleNavKeyDown(e, i)}
              >
                {humanizeSectionId(id)}
              </button>
            ))}
          </div>
          {manifest && (
            <p className="sa-nav-meta mono">
              corpus v{manifest.version} · reviewed {manifest.last_reviewed}
            </p>
          )}
        </nav>

        <div className="sa-workspace">
          {manifestError && (
            <div className="sa-error-block">
              <p className="sa-error mono">// Could not load section list — {manifestError.message}</p>
            </div>
          )}

          {section === 'overview' ? (
            <OverviewSection onDrill={goToSection} corpusVersion={manifest?.version} />
          ) : section === 'mitre_attack' ? (
            <MitreSection />
          ) : section === 'threat_scenarios' ? (
            <ThreatScenariosSection corpusVersion={manifest?.version} />
          ) : section === 'system_architecture' ? (
            <ArchitectureGraphSection
              selectedNodeId={selectedNodeId}
              onSelectNode={selectNode}
              onClearSelection={clearSelection}
            />
          ) : section === 'trust_boundaries' ? (
            <TrustBoundariesSection />
          ) : section === 'attack_surface' ? (
            <AttackSurfaceSection />
          ) : section === 'risks' ? (
            <RiskRegisterSection filters={filters} onFilterChange={setFilters} corpusVersion={manifest?.version} />
          ) : section === 'security_decisions' ? (
            <DecisionsSection />
          ) : section === 'abuse_cases' ? (
            <AbuseCasesSection />
          ) : section === 'reviews' ? (
            <ReviewHistorySection />
          ) : section === 'stale' ? (
            <StaleRecordsSection onOpenSection={goToSection} />
          ) : (
            <GenericSection sectionId={section} filters={filters} onFilterChange={setFilters} />
          )}
        </div>

        {section !== 'system_architecture' && (
          <aside className="sa-rail" aria-label="Context">
            <div className="sa-rail-head">
              <h2 className="sa-subsection-label mono">CONTEXT</h2>
            </div>
            {selectedNodeId ? (
              <ContextRail nodeId={selectedNodeId} onClose={clearSelection} />
            ) : (
              <div className="sa-rail-empty">
                <p>Select a technique, control, or risk to see related context here.</p>
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  )
}
