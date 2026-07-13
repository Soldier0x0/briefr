import { useEffect, useState } from 'react'
import { fetchSecurityArchitectureSection } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
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
 * data, not mocked, just a plain table instead of the typed
 * matrix/timeline/graph components later phases add.
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
        <ul className="sa-row-list" aria-label={`${humanizeSectionId(sectionId)} records`}>
          {items.map((item, i) => (
            <li key={item.id || (item.method ? `${item.method}-${item.path}` : item.path) || i} className="sa-row">
              <div className="sa-row-main">
                <span className="sa-row-title">{item.title || item.path || item.id}</span>
                {item.method && <span className="sa-row-tag mono">{item.method}</span>}
                {item.origin && <span className={`sa-row-origin sa-row-origin-${item.origin} mono`}>{item.origin}</span>}
                {typeof item.active === 'boolean' && (
                  <span className={`sa-active-flag sa-active-${item.active} mono`} title={item.live_flag ? `live_flag: ${item.live_flag}` : 'structural control (always active)'}>
                    {item.active ? 'ACTIVE' : 'INACTIVE'}
                  </span>
                )}
                {item.status && <span className="sa-row-tag mono">{item.status}</span>}
                {item.severity && <span className="sa-row-tag mono">{item.severity}</span>}
                {item.matched_term && <span className="sa-row-tag sa-row-tag-term mono">term: {item.matched_term}</span>}
              </div>
              {item.summary && <p className="sa-row-summary">{item.summary}</p>}
            </li>
          ))}
        </ul>
      </AsyncState>
      {data && (
        <p className="sa-section-count mono">{data.count} record{data.count === 1 ? '' : 's'}</p>
      )}
    </div>
  )
}
