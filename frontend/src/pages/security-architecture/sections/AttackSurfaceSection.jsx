import { useEffect, useMemo, useState } from 'react'
import { fetchSecurityArchitectureAttackSurface } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'
import ArchDataGrid from '../shared/ArchDataGrid.jsx'

const REVIEWED_HELP = 'At least one curated control\'s related_apis covers this endpoint.'
const UNREVIEWED_HELP = 'No curated control record covers this endpoint yet — not a vulnerability finding, just an unreviewed row.'

/**
 * Attack Surface (spec §8 TM-4): generated endpoint inventory × linked controls.
 */
export default function AttackSurfaceSection() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [onlyUnreviewed, setOnlyUnreviewed] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureAttackSurface()
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

  const endpoints = data?.endpoints || []
  const rows = onlyUnreviewed ? endpoints.filter(e => e.linked_control_count === 0) : endpoints

  const columns = useMemo(() => [
    { id: 'method', label: 'Method', width: 90 },
    { id: 'path', label: 'Path', minWidth: 260 },
    {
      id: 'linked_control_count', label: 'Controls', width: 110,
      sortValue: (r) => r.linked_control_count ?? 0,
      render: (r) => (
        <Tooltip text={r.linked_control_count > 0 ? REVIEWED_HELP : UNREVIEWED_HELP}>
          <span className={`sa-active-flag sa-active-${r.linked_control_count > 0} mono`}>
            {r.linked_control_count} control{r.linked_control_count === 1 ? '' : 's'}
          </span>
        </Tooltip>
      ),
    },
    {
      id: 'linked_control_ids', label: 'Linked IDs', minWidth: 200,
      sortable: false,
      render: (r) => (r.linked_control_ids || []).join(', ') || '—',
    },
  ], [])

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">ATTACK SURFACE</h2>
        {data && (
          <p className="sa-mitre-counts mono">
            {data.reviewed_endpoints}/{data.total_endpoints} endpoints have a linked control
          </p>
        )}
      </div>

      <div className="sa-type-tabs mono" role="tablist" aria-label="Attack surface filter">
        <button
          type="button" role="tab" aria-selected={!onlyUnreviewed}
          className={`sa-type-tab${!onlyUnreviewed ? ' active' : ''}`}
          onClick={() => setOnlyUnreviewed(false)}
        >
          ALL
        </button>
        <button
          type="button" role="tab" aria-selected={onlyUnreviewed}
          className={`sa-type-tab${onlyUnreviewed ? ' active' : ''}`}
          onClick={() => setOnlyUnreviewed(true)}
        >
          UNREVIEWED ({data?.unreviewed_endpoints ?? 0})
        </button>
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && rows.length === 0)}
        emptyTitle={error ? undefined : 'No endpoints in the generated inventory.'}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <ArchDataGrid
          gridId="sa-attack-surface"
          columns={columns}
          rows={rows}
          rowKey={(r) => `${r.method}-${r.path}`}
          emptyMessage="No endpoints"
        />
      </AsyncState>
    </div>
  )
}
