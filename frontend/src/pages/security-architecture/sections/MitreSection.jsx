import { useEffect, useMemo, useState } from 'react'
import { fetchSecurityArchitectureMitre } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'
import ArchDataGrid from '../shared/ArchDataGrid.jsx'

const STATUS_LABEL = { yours: 'YOURS', community: 'COMMUNITY', gap: 'GAP' }
const STATUS_HELP = {
  yours: 'At least one saved hunt pack exists for this technique.',
  community: 'The bundled community Sigma/SIEM template library covers this technique.',
  gap: 'No saved or bundled detection content covers this technique — a real detection-engineering gap.',
}

/**
 * MITRE ATT&CK section (TM-3, spec §5.6). Live coverage matrix grouped by tactic.
 */
export default function MitreSection() {
  const [stackInput, setStackInput] = useState('')
  const [stack, setStack] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureMitre(stack)
      .then(res => { if (!cancelled) setData(res) })
      .catch(err => {
        if (!cancelled) {
          setError(err)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [stack, reloadKey])

  const techniques = data?.techniques || []
  const byTactic = techniques.reduce((acc, t) => {
    const key = t.tactic || 'unclassified'
    ;(acc[key] ||= []).push(t)
    return acc
  }, {})

  const columns = useMemo(() => [
    {
      id: 'technique', label: 'Technique', minWidth: 260,
      sortValue: (r) => r.technique_id,
      render: (r) => (
        <a
          className="sa-row-title sa-mitre-link"
          href={`/?view=coverage&technique=${encodeURIComponent(r.technique_id)}`}
          title="Open in Forge"
        >
          {r.technique_id} — {r.name || r.technique_id}
        </a>
      ),
    },
    {
      id: 'status', label: 'Coverage', width: 130,
      render: (r) => (
        <Tooltip text={STATUS_HELP[r.status] || r.status}>
          <span className={`sa-status-chip sa-status-${r.status} mono`}>
            {STATUS_LABEL[r.status] || r.status}
          </span>
        </Tooltip>
      ),
    },
    { id: 'cve_count', label: 'CVEs', width: 80, sortValue: (r) => r.cve_count ?? 0 },
    {
      id: 'kev_count', label: 'KEV', width: 80,
      sortValue: (r) => r.kev_count ?? 0,
      render: (r) => (r.kev_count > 0 ? <span className="sa-row-tag sa-row-tag-kev mono">{r.kev_count}</span> : '—'),
    },
  ], [])

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">MITRE ATT&amp;CK</h2>
        {data?.meta?.counts && (
          <p className="sa-mitre-counts mono">
            {data.meta.counts.gap} gap · {data.meta.counts.community} community · {data.meta.counts.yours} yours
          </p>
        )}
      </div>

      <form
        className="sa-stack-filter"
        onSubmit={(e) => { e.preventDefault(); setStack(stackInput.trim()) }}
      >
        <label className="sa-subsection-label mono" htmlFor="sa-mitre-stack">STACK FILTER</label>
        <input
          id="sa-mitre-stack"
          type="text"
          className="sa-stack-input mono"
          placeholder="e.g. apache, log4j (comma-separated, same matching as Forge)"
          value={stackInput}
          onChange={(e) => setStackInput(e.target.value)}
        />
        <button type="submit" className="admin-btn admin-btn-ghost mono">APPLY</button>
        {stack && (
          <button
            type="button"
            className="admin-btn admin-btn-ghost mono"
            onClick={() => { setStackInput(''); setStack('') }}
          >
            CLEAR
          </button>
        )}
      </form>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && techniques.length === 0)}
        emptyTitle={error ? undefined : 'No techniques linked to CVEs in the database yet.'}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        {Object.entries(byTactic).sort(([a], [b]) => a.localeCompare(b)).map(([tactic, items]) => (
          <div key={tactic} className="sa-mitre-tactic-group">
            <h3 className="sa-subsection-label mono">{tactic.toUpperCase()}</h3>
            <ArchDataGrid
              gridId={`sa-mitre-${tactic}`}
              columns={columns}
              rows={items}
              rowKey={(r) => r.technique_id}
              emptyMessage="No techniques"
            />
          </div>
        ))}
      </AsyncState>
    </div>
  )
}
