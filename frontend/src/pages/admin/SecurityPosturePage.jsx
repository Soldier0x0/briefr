import { useCallback, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import OverviewSection from '../security-architecture/sections/OverviewSection.jsx'
import ArchitectureGraphSection from '../security-architecture/sections/ArchitectureGraphSection.jsx'
import TrustBoundariesSection from '../security-architecture/sections/TrustBoundariesSection.jsx'
import AttackSurfaceSection from '../security-architecture/sections/AttackSurfaceSection.jsx'
import RiskRegisterSection from '../security-architecture/sections/RiskRegisterSection.jsx'
import {
  humanizeSectionId,
  isAnalystHiddenSection,
  resolveAnalystSection,
} from '../security-architecture/constants.js'
import '../security-architecture/SecurityArchitecturePage.css'
import './SecurityPosturePage.css'

/** PM-4a: posture sections hosted under Admin (ARCH tab remains until PM-4c). */
export const POSTURE_SECTIONS = [
  'overview',
  'system_architecture',
  'trust_boundaries',
  'attack_surface',
  'risks',
]

const DEFAULT_SECTION = 'overview'

/**
 * Admin → Security posture: embeds the operator-facing ARCH surfaces
 * (Overview, System Architecture, Trust Boundaries, Attack Surface, Risks)
 * inside Admin chrome. Deep links: `/admin?p=securityposture&section=…&node=…`.
 */
export default function SecurityPosturePage({ mode = 'operator' }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const sectionParam = searchParams.get('section') || DEFAULT_SECTION
  const section = POSTURE_SECTIONS.includes(sectionParam) ? sectionParam : DEFAULT_SECTION
  const selectedNodeId = searchParams.get('node') || ''

  const filters = useMemo(() => ({
    type: searchParams.get('type') || '',
    status: searchParams.get('status') || '',
    severity: searchParams.get('severity') || '',
    origin: searchParams.get('origin') || '',
  }), [searchParams])

  const setSection = useCallback((nextSection, nextFilters = {}) => {
    // PM-4b: ADR / Reviews / Components stay out of the product UI.
    if (isAnalystHiddenSection(nextSection)) {
      nextSection = DEFAULT_SECTION
      nextFilters = {}
    }

    if (!POSTURE_SECTIONS.includes(nextSection)) {
      // Overview tiles may drill to ARCH-only sections (controls, stale, …)
      // — send them to the stand-alone ARCH route until PM-4c retires that shell.
      const params = new URLSearchParams({ section: resolveAnalystSection(nextSection) })
      for (const [key, value] of Object.entries(nextFilters)) {
        if (value !== undefined && value !== null && value !== '') {
          params.set(key, String(value))
        }
      }
      window.location.assign(`/security-architecture?${params}`)
      return
    }
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.set('p', 'securityposture')
      next.set('section', nextSection)
      next.delete('node')
      for (const key of ['type', 'status', 'severity', 'origin']) {
        next.delete(key)
      }
      for (const [key, value] of Object.entries(nextFilters)) {
        if (value !== undefined && value !== null && value !== '') {
          next.set(key, String(value))
        }
      }
      return next
    })
  }, [setSearchParams])

  const setFilters = useCallback((nextFilters) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.set('p', 'securityposture')
      next.set('section', section)
      for (const [key, value] of Object.entries(nextFilters)) {
        if (value !== undefined && value !== null && value !== '') {
          next.set(key, String(value))
        } else {
          next.delete(key)
        }
      }
      return next
    })
  }, [section, setSearchParams])

  const selectNode = useCallback((nodeId) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.set('p', 'securityposture')
      next.set('section', 'system_architecture')
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

  return (
    <div
      className={[
        'admin-security-posture',
        'sa-root',
        section === 'system_architecture' ? 'admin-security-posture--graph' : '',
      ].filter(Boolean).join(' ')}
    >
      <div className="admin-page-header">
        <div>
          <h2>Security posture</h2>
          <p className="admin-page-desc">
            Platform architecture, trust boundaries, attack surface, and risk register
            {mode === 'analyst' ? ' (read-only)' : ''}.
            {' '}Full ARCH workspace (all sections) remains at{' '}
            <Link to="/security-architecture">/security-architecture</Link>
            {' '}until the ARCH tab is retired (PM-4c).
          </p>
        </div>
      </div>

      <div className="admin-subtabs" role="tablist" aria-label="Security posture sections">
        {POSTURE_SECTIONS.map(id => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={section === id}
            className={`admin-subtab${section === id ? ' active' : ''}`}
            onClick={() => setSection(id)}
          >
            {humanizeSectionId(id).toUpperCase()}
          </button>
        ))}
      </div>

      <div className={`sa-shell${section === 'system_architecture' ? ' sa-shell--graph' : ''}`}>
        <div className="sa-workspace admin-security-posture-workspace">
          {section === 'overview' ? (
            <OverviewSection onDrill={setSection} />
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
            <RiskRegisterSection filters={filters} onFilterChange={setFilters} />
          ) : null}
        </div>
      </div>
    </div>
  )
}
