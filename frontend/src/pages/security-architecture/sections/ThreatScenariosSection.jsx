import { useEffect, useState } from 'react'
import {
  fetchSecurityArchitectureSection,
  fetchSecurityArchitectureThreatScenarios,
  fetchUserStack,
} from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'

const CATALOGS = [
  { id: 'operational', label: 'Operational paths' },
  { id: 'stack', label: 'Your stack' },
  { id: 'self-stack', label: 'BRIEFR self-stack' },
]

const STATUS_LABEL = { yours: 'YOURS', community: 'COMMUNITY', gap: 'GAP' }

/**
 * Threat Scenarios section (TM-3, spec §5.10) -- three catalogs behind one
 * toggle, matching Forge's profileStack convention (frontend/src/components/
 * forge/ScenariosView.jsx): "your stack" reads GET /api/me/stack (spec
 * §5.10: "stack filter inherits user stack from /api/me/stack for type 2"),
 * "self-stack" needs no client input at all -- the server resolves the
 * generated self-stack terms from the corpus (§4.5), computed once at
 * corpus-generation time, never recomputed per request (CLAUDE.md danger
 * zone 6). "Operational paths" reuses the existing generic section read
 * (curated threat_scenarios.yaml, currently an empty pre-review stub).
 */
export default function ThreatScenariosSection() {
  const [catalog, setCatalog] = useState('operational')
  const [userStack, setUserStack] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    fetchUserStack()
      .then(res => { if (!cancelled) setUserStack(res?.stack_terms || '') })
      .catch(() => { /* stack catalog just shows its own empty state */ })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    const load = catalog === 'operational'
      ? fetchSecurityArchitectureSection('threat_scenarios', {})
      : fetchSecurityArchitectureThreatScenarios({
        stack: catalog === 'stack' ? userStack : '',
        selfStack: catalog === 'self-stack',
      })

    load
      .then(res => { if (!cancelled) setData(res) })
      .catch(err => {
        if (!cancelled) {
          setError(err)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [catalog, userStack, reloadKey])

  const isCurated = catalog === 'operational'
  const rows = isCurated ? (data?.items || []) : (data?.scenarios || [])
  const needsProfile = catalog === 'stack' && !userStack

  return (
    <div className="sa-section">
      <h2 className="sa-section-title mono">THREAT SCENARIOS</h2>

      <div className="sa-type-tabs mono" role="tablist" aria-label="Scenario catalog">
        {CATALOGS.map(c => (
          <button
            key={c.id}
            type="button"
            role="tab"
            aria-selected={catalog === c.id}
            className={`sa-type-tab${catalog === c.id ? ' active' : ''}`}
            onClick={() => setCatalog(c.id)}
          >
            {c.label}
          </button>
        ))}
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || needsProfile || (!loading && rows.length === 0)}
        emptyTitle={
          error
            ? undefined
            : needsProfile
              ? 'Save an asset stack on your profile (Me → Stack) to see stack-scoped scenarios.'
              : isCurated
                ? 'No operational scenarios yet — curated, empty until a security-review pass populates threat_scenarios.yaml.'
                : 'No ATT&CK techniques linked to CVEs matching this stack yet.'
        }
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        {isCurated ? (
          <ul className="sa-row-list" aria-label="Operational threat scenarios">
            {rows.map(item => (
              <li key={item.id} className="sa-row">
                <div className="sa-row-main">
                  <span className="sa-row-title">{item.title}</span>
                  {item.origin && <span className={`sa-row-origin sa-row-origin-${item.origin} mono`}>{item.origin}</span>}
                </div>
                {item.summary && <p className="sa-row-summary">{item.summary}</p>}
              </li>
            ))}
          </ul>
        ) : (
          <ul className="sa-row-list" aria-label="Stack-scoped threat scenarios">
            {rows.map(scenario => (
              <li key={scenario.technique_id} className="sa-row">
                <div className="sa-row-main">
                  <a
                    className="sa-row-title sa-mitre-link"
                    href={`/?view=scenarios&technique=${encodeURIComponent(scenario.technique_id)}`}
                    title="Open in Forge"
                  >
                    {scenario.technique_id} — {scenario.name}
                  </a>
                  <span className={`sa-status-chip sa-status-${scenario.coverage_status} mono`}>
                    {STATUS_LABEL[scenario.coverage_status] || scenario.coverage_status}
                  </span>
                  {scenario.kev_count > 0 && <span className="sa-row-tag sa-row-tag-kev mono">{scenario.kev_count} KEV</span>}
                </div>
                <p className="sa-row-summary">{scenario.scenario}</p>
              </li>
            ))}
          </ul>
        )}
      </AsyncState>
      {data?.meta?.stack_terms?.length > 0 && catalog !== 'operational' && (
        <p className="sa-section-count mono">
          matched terms: {data.meta.stack_terms.join(', ')}
        </p>
      )}
    </div>
  )
}
