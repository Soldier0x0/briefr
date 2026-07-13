import { useEffect, useMemo, useState } from 'react'
import { fetchSecurityArchitectureSection } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'
import AdminDataGrid from '../../admin/shared/AdminDataGrid.jsx'
import { downloadCsv, exportFilename } from '../../../utils/exportCsv.js'
import { downloadRiskRegisterPdf } from '../../../utils/securityArchitecturePdf.js'

const STALE_HELP = 'This curated row has not been reviewed in over 90 days -- it is excluded from every coverage/compliance percentage until re-reviewed (spec §4.1 staleness decay).'
const ORIGIN_HELP = {
  curated: 'A human judgment call recorded during a security-review pass.',
  live: 'Auto-derived from a live KEV/critical CVE hit on BRIEFR\'s own generated self-stack -- cannot be closed by hand, closes itself when the CVE stops matching.',
}

function riskCsvRows(rows) {
  const header = ['ID', 'Title', 'Category', 'Severity', 'Status', 'Origin', 'Stale', 'Review Date', 'Matched Term', 'Summary']
  const body = rows.map(r => [
    r.id ?? '', r.title ?? '', r.category ?? '', r.severity ?? '', r.status ?? '',
    r.origin ?? '', r.stale ? 'yes' : 'no', r.review_date ?? '', r.matched_term ?? '', r.summary ?? '',
  ])
  return [header, ...body]
    .map(row => row.map(v => {
      const s = String(v ?? '')
      return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
    }).join(','))
    .join('\n')
}

/**
 * Risk Register (spec §5.12, §8 TM-5): AdminDataGrid wrapper over curated +
 * live risk rows. Two row origins render distinctly (curated vs live, spec
 * §5.12) and every curated row carries a visible STALE badge sourced from
 * the server's `stale` flag (security_architecture/merge.py::annotate_stale)
 * -- never recomputed here, so the badge and the Overview "Controls Active"
 * percentage math always agree on which rows are stale.
 */
export default function RiskRegisterSection({ filters, onFilterChange, corpusVersion }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureSection('risks', filters)
      .then(res => { if (!cancelled) setData(res) })
      .catch(err => {
        if (!cancelled) {
          setError(err)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [filters.status, filters.severity, filters.origin, reloadKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const rows = data?.items || []
  const staleCount = rows.filter(r => r.stale).length

  const columns = useMemo(() => [
    {
      id: 'title', label: 'Risk', minWidth: 220,
      render: (r) => (
        <span>
          {r.title}
          {r.stale && (
            <Tooltip text={STALE_HELP}>
              <span className="sa-status-chip sa-status-critical mono" style={{ marginLeft: 6 }}>STALE</span>
            </Tooltip>
          )}
        </span>
      ),
    },
    { id: 'category', label: 'Category', width: 140 },
    { id: 'severity', label: 'Severity', width: 100, render: (r) => r.severity ? r.severity.toUpperCase() : '—' },
    { id: 'status', label: 'Status', width: 100 },
    {
      id: 'origin', label: 'Origin', width: 100,
      render: (r) => (
        <Tooltip text={ORIGIN_HELP[r.origin] || ''}>
          <span className={`sa-row-origin sa-row-origin-${r.origin} mono`}>{r.origin}</span>
        </Tooltip>
      ),
    },
    { id: 'review_date', label: 'Review Date', width: 110, render: (r) => r.review_date || '—' },
    { id: 'owner', label: 'Owner', width: 110, render: (r) => r.owner || '—' },
    { id: 'matched_term', label: 'Matched Term', width: 130, render: (r) => r.matched_term || '—' },
    { id: 'summary', label: 'Mitigation / Summary', minWidth: 260, render: (r) => r.summary || '—' },
  ], [])

  const activeFilters = ['status', 'severity', 'origin'].filter(k => filters[k])

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">RISK REGISTER</h2>
        {data && (
          <p className="sa-mitre-counts mono">
            {data.count} row{data.count === 1 ? '' : 's'}{staleCount > 0 ? ` · ${staleCount} stale` : ''}
          </p>
        )}
      </div>

      {activeFilters.length > 0 && (
        <div className="sa-active-filters mono">
          {activeFilters.map(k => (
            <span key={k} className="sa-filter-chip">
              {k}={filters[k]}
              <button
                type="button"
                className="sa-filter-chip-clear"
                aria-label={`Clear ${k} filter`}
                onClick={() => onFilterChange({ ...filters, [k]: undefined })}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="sa-type-tabs mono" role="tablist" aria-label="Origin filter">
        {['', 'curated', 'live'].map(o => (
          <button
            key={o || 'all'}
            type="button" role="tab" aria-selected={(filters.origin || '') === o}
            className={`sa-type-tab${(filters.origin || '') === o ? ' active' : ''}`}
            onClick={() => onFilterChange({ ...filters, origin: o || undefined })}
          >
            {o ? o.toUpperCase() : 'ALL'}
          </button>
        ))}
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && rows.length === 0)}
        emptyTitle={
          error
            ? undefined
            : 'No risk rows yet — the curated register is empty until a real risk-review pass populates risks.yaml, and no live self-stack KEV/critical CVE hits are matching right now.'
        }
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <AdminDataGrid
          gridId="sa-risk-register"
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          emptyMessage="No risk rows"
          toolbarExtra={
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button" className="admin-btn admin-btn-ghost mono"
                onClick={() => downloadCsv(riskCsvRows(rows), exportFilename())}
                disabled={!rows.length}
              >
                EXPORT CSV
              </button>
              <button
                type="button" className="admin-btn admin-btn-ghost mono"
                onClick={() => downloadRiskRegisterPdf(rows, { corpusVersion })}
                disabled={!rows.length}
              >
                EXPORT PDF
              </button>
            </div>
          }
        />
      </AsyncState>
    </div>
  )
}
