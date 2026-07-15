import { useEffect, useMemo, useState } from 'react'
import { fetchSecurityArchitectureSection } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'
import ArchDataGrid from '../shared/ArchDataGrid.jsx'

const STALE_HELP = 'This review record has not been refreshed in over 90 days (spec §4.1 staleness decay).'
const ORIGIN_HELP = {
  curated: 'A recorded security-review pass (architecture review, threat model review, ...).',
  live: 'A security-relevant audit_log event (auth, backup, config, restart, scheduler, integrity) -- same table and redaction rule as the Admin Audit Log.',
}

function eventTimestamp(item) {
  return item.review_date || item.occurred_at || ''
}

/**
 * Review History (spec §5.14, §8 TM-5).
 */
export default function ReviewHistorySection() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [selectedId, setSelectedId] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureSection('reviews', {})
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

  const rows = [...(data?.items || [])].sort((a, b) => (eventTimestamp(b) > eventTimestamp(a) ? 1 : -1))
  const selected = rows.find(r => r.id === selectedId)

  const columns = useMemo(() => [
    {
      id: 'title', label: 'Event', minWidth: 220,
      render: (r) => r.title || r.action || '—',
    },
    {
      id: 'origin', label: 'Origin', width: 100,
      render: (r) => (
        <Tooltip text={ORIGIN_HELP[r.origin] || ''}>
          <span className={`sa-row-origin sa-row-origin-${r.origin} mono`}>{r.origin}</span>
        </Tooltip>
      ),
    },
    { id: 'review_type', label: 'Type', width: 120, render: (r) => r.review_type || '—' },
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
    {
      id: 'when', label: 'When', width: 140,
      sortValue: (r) => eventTimestamp(r),
      render: (r) => eventTimestamp(r) || '—',
    },
    { id: 'summary', label: 'Summary', minWidth: 260, render: (r) => r.summary || '—' },
  ], [])

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">REVIEW HISTORY</h2>
        {data && <p className="sa-mitre-counts mono">{rows.length} event{rows.length === 1 ? '' : 's'}</p>}
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && rows.length === 0)}
        emptyTitle={error ? undefined : 'No review events yet — no curated review passes recorded and no matching security audit-log entries.'}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <ArchDataGrid
          gridId="sa-review-history"
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          emptyMessage="No review events"
          onRowClick={(r) => setSelectedId(prev => (prev === r.id ? null : r.id))}
          activeRowKey={selectedId}
        />
        {selected && (
          <div className="sa-arch-grid-detail">
            {selected.outcome && (
              <div className="sa-decision-field">
                <h4 className="sa-subsection-label mono">OUTCOME</h4>
                <p>{selected.outcome}</p>
              </div>
            )}
            {Array.isArray(selected.participants) && selected.participants.length > 0 && (
              <p className="sa-rail-meta mono">participants: {selected.participants.join(', ')}</p>
            )}
            {selected.actor && selected.origin === 'live' && (
              <p className="sa-rail-meta mono">actor: {selected.actor}{selected.target ? ` — target: ${selected.target}` : ''}</p>
            )}
          </div>
        )}
      </AsyncState>
    </div>
  )
}
