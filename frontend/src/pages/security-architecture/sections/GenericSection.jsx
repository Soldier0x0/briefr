import { useEffect, useMemo, useState } from 'react'
import { fetchSecurityArchitectureSection } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import ArchDataGrid from '../shared/ArchDataGrid.jsx'
import { humanizeSectionId } from '../constants.js'

const TYPE_LABELS = {
  components: 'Routers',
  endpoints: 'Endpoints',
  jobs: 'Scheduler Jobs',
  tables: 'DB Tables',
}

/**
 * TM-2 stub section view (spec §8 TM-2: "even if that view is just a stub
 * in TM-2, TM-3 builds it out"). Shows the exact corpus rows behind an
 * Overview tile click via the generic GET /section/{id} endpoint -- real
 * data, not mocked, via the shared ArchDataGrid primitive (E5-2).
 */
export default function GenericSection({ sectionId, filters, onFilterChange }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureSection(sectionId, filters)
      .then(res => { if (!cancelled) setData(res) })
      .catch(err => {
        if (!cancelled) {
          setError(err)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [sectionId, filters.type, filters.status, filters.severity, filters.origin, reloadKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const items = data?.items || []
  const activeFilters = ['status', 'severity', 'origin'].filter(k => filters[k])
  const resolvedType = data?.type || ''

  const columns = useMemo(() => {
    if (resolvedType === 'endpoints') {
      return [
        { id: 'method', label: 'Method', width: 90 },
        { id: 'path', label: 'Path', minWidth: 220, render: (r) => r.path || r.title || r.id },
        { id: 'summary', label: 'Summary', minWidth: 260, render: (r) => r.summary || '—' },
      ]
    }
    if (resolvedType === 'components' || resolvedType === 'jobs' || resolvedType === 'tables') {
      return [
        { id: 'id', label: 'ID', width: 160, render: (r) => r.id || '—' },
        { id: 'title', label: 'Title', minWidth: 200, render: (r) => r.title || r.path || '—' },
        { id: 'summary', label: 'Summary', minWidth: 280, render: (r) => r.summary || '—' },
      ]
    }
    return [
      {
        id: 'title', label: 'Title', minWidth: 200,
        render: (r) => r.title || r.path || r.id || '—',
      },
      { id: 'status', label: 'Status', width: 100, render: (r) => r.status || '—' },
      { id: 'severity', label: 'Severity', width: 100, render: (r) => r.severity || '—' },
      {
        id: 'origin', label: 'Origin', width: 100,
        render: (r) => (r.origin ? <span className={`sa-row-origin sa-row-origin-${r.origin} mono`}>{r.origin}</span> : '—'),
      },
      {
        id: 'active', label: 'Active', width: 100,
        render: (r) => (
          typeof r.active === 'boolean'
            ? (
              <span className={`sa-active-flag sa-active-${r.active} mono`} title={r.live_flag ? `live_flag: ${r.live_flag}` : 'structural control'}>
                {r.active ? 'ACTIVE' : 'INACTIVE'}
              </span>
            )
            : '—'
        ),
      },
      {
        id: 'matched_term', label: 'Term', width: 120,
        render: (r) => r.matched_term || '—',
      },
      { id: 'summary', label: 'Summary', minWidth: 260, render: (r) => r.summary || '—' },
    ]
  }, [resolvedType])

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">{humanizeSectionId(sectionId).toUpperCase()}</h2>
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
      </div>

      {data?.available_types?.length > 1 && (
        <div className="sa-type-tabs mono" role="tablist" aria-label="Collection">
          {data.available_types.map(t => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={data.type === t}
              className={`sa-type-tab${data.type === t ? ' active' : ''}`}
              onClick={() => onFilterChange({ ...filters, type: t })}
            >
              {TYPE_LABELS[t] || t}
            </button>
          ))}
        </div>
      )}

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && items.length === 0)}
        emptyTitle={
          error
            ? undefined
            : 'No records yet — this section is curated and empty until a security-review pass populates it (TM-3+).'
        }
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <ArchDataGrid
          gridId={`sa-generic-${sectionId}-${resolvedType || 'default'}`}
          columns={columns}
          rows={items}
          rowKey={(r, i) => r.id || (r.method ? `${r.method}-${r.path}` : r.path) || i}
          emptyMessage="No records"
        />
      </AsyncState>
      {data && (
        <p className="sa-section-count mono">{data.count} record{data.count === 1 ? '' : 's'}</p>
      )}
    </div>
  )
}
