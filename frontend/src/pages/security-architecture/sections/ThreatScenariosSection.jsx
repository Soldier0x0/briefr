import { useEffect, useMemo, useState } from 'react'
import {
  fetchSecurityArchitectureSection,
  fetchSecurityArchitectureThreatScenarios,
  fetchUserStack,
} from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import ArchDataGrid from '../shared/ArchDataGrid.jsx'
import { downloadScenarioPdf } from '../../../utils/securityArchitecturePdf.js'

const CATALOGS = [
  { id: 'operational', label: 'Operational paths' },
  { id: 'stack', label: 'Your stack' },
  { id: 'self-stack', label: 'BRIEFR self-stack' },
]

const STATUS_LABEL = { yours: 'YOURS', community: 'COMMUNITY', gap: 'GAP' }

/**
 * Threat Scenarios section (TM-3, spec §5.10).
 */
export default function ThreatScenariosSection({ corpusVersion } = {}) {
  const [catalog, setCatalog] = useState('self-stack')
  const [userStack, setUserStack] = useState('')
  const [operationalCount, setOperationalCount] = useState(null)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  const visibleCatalogs = useMemo(() => (
    CATALOGS.filter((c) => c.id !== 'operational' || (operationalCount ?? 0) > 0)
  ), [operationalCount])

  useEffect(() => {
    let cancelled = false
    fetchUserStack()
      .then(res => { if (!cancelled) setUserStack(res?.stack_terms || '') })
      .catch(() => { /* stack catalog just shows its own empty state */ })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchSecurityArchitectureSection('threat_scenarios', {})
      .then(res => { if (!cancelled) setOperationalCount((res?.items || []).length) })
      .catch(() => { if (!cancelled) setOperationalCount(0) })
    return () => { cancelled = true }
  }, [reloadKey])

  useEffect(() => {
    if (operationalCount === null) return
    if (!visibleCatalogs.some(c => c.id === catalog)) {
      setCatalog(visibleCatalogs[0]?.id || 'self-stack')
    }
  }, [operationalCount, visibleCatalogs, catalog])

  useEffect(() => {
    if (catalog === 'stack' && !userStack) {
      setData(null)
      setLoading(false)
      setError(null)
      return undefined
    }

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

  const curatedColumns = useMemo(() => [
    { id: 'title', label: 'Scenario', minWidth: 220 },
    {
      id: 'origin', label: 'Origin', width: 100,
      render: (r) => (r.origin ? <span className={`sa-row-origin sa-row-origin-${r.origin} mono`}>{r.origin}</span> : '—'),
    },
    {
      id: 'export', label: 'Export', width: 110, sortable: false,
      render: (r) => (
        <button
          type="button"
          className="sa-row-tag mono"
          onClick={(e) => { e.stopPropagation(); downloadScenarioPdf(r, { corpusVersion }) }}
        >
          EXPORT PDF
        </button>
      ),
    },
    { id: 'summary', label: 'Summary', minWidth: 280, render: (r) => r.summary || '—' },
  ], [corpusVersion])

  const stackColumns = useMemo(() => [
    {
      id: 'technique', label: 'Technique', minWidth: 240,
      sortValue: (r) => r.technique_id,
      render: (r) => (
        <a
          className="sa-row-title sa-mitre-link"
          href={`/?view=scenarios&technique=${encodeURIComponent(r.technique_id)}`}
          title="Open in Forge"
        >
          {r.technique_id} — {r.name}
        </a>
      ),
    },
    {
      id: 'coverage_status', label: 'Coverage', width: 130,
      render: (r) => (
        <span className={`sa-status-chip sa-status-${r.coverage_status} mono`}>
          {STATUS_LABEL[r.coverage_status] || r.coverage_status}
        </span>
      ),
    },
    {
      id: 'kev_count', label: 'KEV', width: 80,
      sortValue: (r) => r.kev_count ?? 0,
      render: (r) => (r.kev_count > 0 ? <span className="sa-row-tag sa-row-tag-kev mono">{r.kev_count}</span> : '—'),
    },
    {
      id: 'export', label: 'Export', width: 110, sortable: false,
      render: (r) => (
        <button
          type="button"
          className="sa-row-tag mono"
          onClick={(e) => { e.stopPropagation(); downloadScenarioPdf(r, { corpusVersion }) }}
        >
          EXPORT PDF
        </button>
      ),
    },
    { id: 'scenario', label: 'Scenario', minWidth: 300, render: (r) => r.scenario || '—' },
  ], [corpusVersion])

  return (
    <div className="sa-section">
      <h2 className="sa-section-title mono">THREAT SCENARIOS</h2>

      {visibleCatalogs.length > 1 && (
        <div className="sa-type-tabs mono" role="tablist" aria-label="Scenario catalog">
          {visibleCatalogs.map(c => (
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
      )}

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
        <ArchDataGrid
          gridId={`sa-threat-scenarios-${catalog}`}
          columns={isCurated ? curatedColumns : stackColumns}
          rows={rows}
          rowKey={(r) => r.id || r.technique_id}
          emptyMessage="No scenarios"
        />
      </AsyncState>
      {data?.meta?.stack_terms?.length > 0 && catalog !== 'operational' && (
        <p className="sa-section-count mono">
          matched terms: {data.meta.stack_terms.join(', ')}
        </p>
      )}
    </div>
  )
}
