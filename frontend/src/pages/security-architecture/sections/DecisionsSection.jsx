import { useEffect, useMemo, useState } from 'react'
import { fetchSecurityArchitectureSection } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'
import ArchDataGrid from '../shared/ArchDataGrid.jsx'

const STALE_HELP = 'This decision record has not been reviewed in over 90 days (spec §4.1 staleness decay).'

/**
 * Security Decision Records (spec §5.13, §8 TM-5).
 */
export default function DecisionsSection() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [selectedId, setSelectedId] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureSection('security_decisions', {})
      .then(res => { if (!cancelled) setData(res) })
      .catch(err => {
        if (!cancelled) {
          setError(err)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [reloadKey])

  const rows = data?.items || []
  const selected = rows.find(d => d.id === selectedId)

  const columns = useMemo(() => [
    { id: 'title', label: 'Decision', minWidth: 240 },
    { id: 'status', label: 'Status', width: 100, render: (r) => r.status || '—' },
    {
      id: 'stale', label: 'Review', width: 90,
      sortValue: (r) => (r.stale ? 1 : 0),
      render: (r) => (
        r.stale
          ? (
            <Tooltip text={STALE_HELP}>
              <span className="sa-status-chip sa-status-critical mono">STALE</span>
            </Tooltip>
          )
          : '—'
      ),
    },
    { id: 'summary', label: 'Summary', minWidth: 300, render: (r) => r.summary || '—' },
  ], [])

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">SECURITY DECISIONS</h2>
        {data && <p className="sa-mitre-counts mono">{data.count} record{data.count === 1 ? '' : 's'}</p>}
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && rows.length === 0)}
        emptyTitle={error ? undefined : 'No decision records yet — curated, empty until an ADR is mapped into the corpus.'}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <ArchDataGrid
          gridId="sa-security-decisions"
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          emptyMessage="No decision records"
          onRowClick={(r) => setSelectedId(prev => (prev === r.id ? null : r.id))}
          activeRowKey={selectedId}
        />
        {selected && (
          <div className="sa-arch-grid-detail">
            {selected.decision && (
              <div className="sa-decision-field">
                <h4 className="sa-subsection-label mono">DECISION</h4>
                <p>{selected.decision}</p>
              </div>
            )}
            {Array.isArray(selected.alternatives) && selected.alternatives.length > 0 && (
              <div className="sa-decision-field">
                <h4 className="sa-subsection-label mono">ALTERNATIVES CONSIDERED</h4>
                <ul>
                  {selected.alternatives.map((a, i) => <li key={i}>{a}</li>)}
                </ul>
              </div>
            )}
            {selected.tradeoffs && (
              <div className="sa-decision-field">
                <h4 className="sa-subsection-label mono">TRADEOFFS</h4>
                <p>{selected.tradeoffs}</p>
              </div>
            )}
            {selected.consequences && (
              <div className="sa-decision-field">
                <h4 className="sa-subsection-label mono">CONSEQUENCES</h4>
                <p>{selected.consequences}</p>
              </div>
            )}
            {selected.adr_ref && (
              <p className="sa-decision-source mono">source: {selected.adr_ref}</p>
            )}
          </div>
        )}
      </AsyncState>
    </div>
  )
}
