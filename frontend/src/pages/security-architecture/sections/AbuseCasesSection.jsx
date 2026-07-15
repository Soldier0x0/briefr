import { useEffect, useMemo, useState } from 'react'
import { fetchSecurityArchitectureSection } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'
import ArchDataGrid from '../shared/ArchDataGrid.jsx'

const STALE_HELP = 'This abuse case has not been reviewed in over 90 days (spec §4.1 staleness decay).'
const STATUS_HELP = {
  mitigated: 'Real protection code exists and is cited as evidence.',
  partial: 'Some protection exists but a gap remains -- see "Remaining risk".',
  open: 'No mitigating control exists yet -- an honest, unmitigated finding.',
}

/**
 * Abuse Case Catalog (spec §5.11, §8 TM-5).
 */
export default function AbuseCasesSection() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureSection('abuse_cases', {})
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

  const allRows = data?.items || []
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return allRows
    return allRows.filter(r =>
      (r.title || '').toLowerCase().includes(q) ||
      (r.summary || '').toLowerCase().includes(q) ||
      (r.category || '').toLowerCase().includes(q),
    )
  }, [allRows, query])

  const selected = rows.find(r => r.id === selectedId)

  const columns = useMemo(() => [
    { id: 'title', label: 'Case', minWidth: 220 },
    { id: 'category', label: 'Category', width: 140, render: (r) => r.category || '—' },
    {
      id: 'status', label: 'Status', width: 110,
      sortValue: (r) => r.status || '',
      render: (r) => (
        r.status
          ? (
            <Tooltip text={STATUS_HELP[r.status] || r.status}>
              <span className={`sa-status-chip sa-status-${r.status === 'open' ? 'critical' : r.status === 'partial' ? 'medium' : 'low'} mono`}>
                {r.status.toUpperCase()}
              </span>
            </Tooltip>
          )
          : '—'
      ),
    },
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
    { id: 'summary', label: 'Summary', minWidth: 280, render: (r) => r.summary || '—' },
  ], [])

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">ABUSE CASES</h2>
        {data && <p className="sa-mitre-counts mono">{allRows.length} case{allRows.length === 1 ? '' : 's'}</p>}
      </div>

      <form className="sa-stack-filter" onSubmit={(e) => e.preventDefault()}>
        <label className="sa-subsection-label mono" htmlFor="sa-abuse-search">SEARCH</label>
        <input
          id="sa-abuse-search"
          type="text"
          className="sa-stack-input mono"
          placeholder="e.g. ssrf, replay, rate limit"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </form>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && rows.length === 0)}
        emptyTitle={
          error
            ? undefined
            : query
              ? `No abuse cases match "${query}".`
              : 'No abuse cases yet — curated, empty until a security-review pass populates abuse_cases.yaml.'
        }
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <ArchDataGrid
          gridId="sa-abuse-cases"
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          emptyMessage="No abuse cases"
          onRowClick={(r) => setSelectedId(prev => (prev === r.id ? null : r.id))}
          activeRowKey={selectedId}
        />
        {selected && (
          <div className="sa-arch-grid-detail">
            {Array.isArray(selected.attack_flow) && selected.attack_flow.length > 0 && (
              <div className="sa-decision-field">
                <h4 className="sa-subsection-label mono">ATTACK FLOW</h4>
                <ol>
                  {selected.attack_flow.map((step, i) => <li key={i}>{step}</li>)}
                </ol>
              </div>
            )}
            {selected.impact && (
              <div className="sa-decision-field">
                <h4 className="sa-subsection-label mono">IMPACT</h4>
                <p>{selected.impact}</p>
              </div>
            )}
            {selected.current_protection && (
              <div className="sa-decision-field">
                <h4 className="sa-subsection-label mono">CURRENT PROTECTION</h4>
                <p>{selected.current_protection}</p>
              </div>
            )}
            {selected.remaining_risk && (
              <div className="sa-decision-field">
                <h4 className="sa-subsection-label mono">REMAINING RISK</h4>
                <p>{selected.remaining_risk}</p>
              </div>
            )}
          </div>
        )}
      </AsyncState>
    </div>
  )
}
