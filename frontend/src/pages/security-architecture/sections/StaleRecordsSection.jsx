import { useEffect, useMemo, useState } from 'react'
import { fetchSecurityArchitectureStale } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import ArchDataGrid from '../shared/ArchDataGrid.jsx'

const SECTION_LABEL = {
  components: 'Components', trust_boundaries: 'Trust Boundaries', controls: 'Controls',
  abuse_cases: 'Abuse Cases', threat_scenarios: 'Threat Scenarios',
  security_decisions: 'Security Decisions', risks: 'Risk Register', reviews: 'Review History',
}

/**
 * Stale Records (spec §5.1 "Stale Records" tile drill-through, §9.6).
 */
export default function StaleRecordsSection({ onOpenSection }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureStale()
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

  const columns = useMemo(() => [
    { id: 'title', label: 'Record', minWidth: 220 },
    {
      id: 'section', label: 'Section', width: 160,
      sortValue: (r) => r.section || '',
      render: (r) => (
        <button
          type="button"
          className="sa-row-tag mono sa-mitre-link"
          onClick={(e) => { e.stopPropagation(); onOpenSection(r.section) }}
          title={`Open ${SECTION_LABEL[r.section] || r.section}`}
        >
          {SECTION_LABEL[r.section] || r.section}
        </button>
      ),
    },
    {
      id: 'stale', label: 'Status', width: 90, sortable: false,
      render: () => <span className="sa-status-chip sa-status-critical mono">STALE</span>,
    },
    { id: 'review_date', label: 'Last Review', width: 120, render: (r) => r.review_date || '—' },
    { id: 'summary', label: 'Summary', minWidth: 260, render: (r) => r.summary || '—' },
  ], [onOpenSection])

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">STALE RECORDS</h2>
        {data && <p className="sa-mitre-counts mono">{data.count} record{data.count === 1 ? '' : 's'} past the 90-day review window</p>}
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && rows.length === 0)}
        emptyTitle={error ? undefined : 'No stale records — every curated record has been reviewed within the last 90 days.'}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <ArchDataGrid
          gridId="sa-stale-records"
          columns={columns}
          rows={rows}
          rowKey={(r, i) => `${r.section}-${r.id || i}`}
          emptyMessage="No stale records"
        />
      </AsyncState>
    </div>
  )
}
