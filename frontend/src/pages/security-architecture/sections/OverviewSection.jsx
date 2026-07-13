import { useEffect, useState } from 'react'
import { fetchSecurityArchitectureOverview } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'

/**
 * Overview (spec §5.1, §8 TM-2): evidence tiles that are counts or ratios
 * whose inputs are visible server-side (backend/security_architecture/
 * routers/security_architecture.py::get_overview) -- no composite grades,
 * no arithmetic invented here. Every tile drills through to the exact
 * corpus rows behind its number via `onDrill(section, filter)`.
 *
 * The "architecture stack" is a simplified view of the generated layer
 * (routers / scheduler jobs / DB tables) -- real corpus data, not the full
 * System Architecture graph (TM-4's interactive pan/zoom graph, backed by
 * graphs/architecture.json, lives in its own nav section). There is no
 * "Frontend" tier here because components.yaml currently only contains
 * backend router modules.
 */
export default function OverviewSection({ onDrill }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureOverview()
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

  const tiles = data?.tiles || []
  const stackTiers = [
    { type: 'components', label: 'API Routers', help: 'FastAPI router modules.' },
    { type: 'jobs', label: 'Scheduler Jobs', help: 'Background jobs registered in scheduler.py.' },
    { type: 'tables', label: 'DB Tables', help: 'Database tables from schema metadata.' },
  ]
  const countByType = {
    components: data?.generated?.components,
    jobs: data?.generated?.scheduler_jobs,
    tables: data?.generated?.db_tables,
  }

  return (
    <div className="sa-section">
      <h2 className="sa-section-title mono">OVERVIEW</h2>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error)}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-tile-row sa-skeleton-row" aria-hidden="true" />}
      >
        <div className="sa-tile-row" role="list" aria-label="Security posture evidence tiles">
          {tiles.map(tile => (
            <div key={tile.id} role="listitem">
              <Tooltip text={tile.help}>
                <button
                  type="button"
                  className="sa-tile"
                  onClick={() => onDrill(tile.section, tile.filter)}
                >
                  <span className="sa-tile-label mono">{tile.label}</span>
                  <span className="sa-tile-value">
                    {tile.value}
                    {tile.unit && <span className="sa-tile-unit"> {tile.unit}</span>}
                  </span>
                </button>
              </Tooltip>
            </div>
          ))}
        </div>
      </AsyncState>

      <div className="sa-arch-stack">
        <h3 className="sa-subsection-label mono">ARCHITECTURE OVERVIEW (SIMPLIFIED)</h3>
        <p className="sa-arch-stack-note">
          Generated layer only — routers, scheduler jobs, and DB tables discovered from code.
          See the System Architecture section for the full interactive graph with edges.
        </p>
        <div className="sa-arch-tiers" role="list" aria-label="Generated architecture tiers">
          {stackTiers.map((tier, i) => (
            <div key={tier.type} className="sa-arch-tier-wrap" role="listitem">
              <Tooltip text={tier.help}>
                <button
                  type="button"
                  className="sa-arch-tier"
                  onClick={() => onDrill('components', { type: tier.type })}
                >
                  <span className="sa-arch-tier-label mono">{tier.label}</span>
                  <span className="sa-arch-tier-count">{countByType[tier.type] ?? '—'}</span>
                </button>
              </Tooltip>
              {i < stackTiers.length - 1 && <span className="sa-arch-tier-arrow" aria-hidden="true">→</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
