import { useEffect, useState } from 'react'
import { fetchSecurityArchitectureOverview } from '../../../api.js'
import { notifyApiError, notifyExportError, notifyExportProgress, notifyExportSuccess } from '../../../components/Toast.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import StatCard from '../../admin/shared/StatCard.jsx'
import { downloadOverviewPdf } from '../../../utils/securityArchitecturePdf.js'

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
export default function OverviewSection({ onDrill, corpusVersion }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [pdfBusy, setPdfBusy] = useState(false)

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

  async function handleExportPdf() {
    if (!data || pdfBusy) return
    setPdfBusy(true)
    notifyExportProgress('Generating overview PDF…')
    try {
      await downloadOverviewPdf({ ...data, corpus_version: corpusVersion })
      notifyExportSuccess('Overview PDF downloaded')
    } catch (err) {
      notifyExportError(err?.message || 'PDF export failed')
    } finally {
      setPdfBusy(false)
    }
  }

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">OVERVIEW</h2>
        <button
          type="button"
          className="admin-btn admin-btn-ghost mono"
          onClick={handleExportPdf}
          disabled={!data || pdfBusy}
        >
          {pdfBusy ? 'EXPORTING…' : 'EXPORT PDF'}
        </button>
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error)}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={
          <div className="sa-stat-grid" aria-hidden="true">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="sa-skeleton-row" />
            ))}
          </div>
        }
      >
        <div className="sa-stat-grid" role="list" aria-label="Security posture evidence tiles">
          {tiles.map(tile => (
            <div key={tile.id} role="listitem" className="sa-stat-card-wrap">
              <Tooltip text={tile.help}>
                <button
                  type="button"
                  className="sa-stat-card-btn"
                  onClick={() => onDrill(tile.section, tile.filter)}
                >
                  <StatCard
                    plain
                    label={tile.label}
                    value={tile.value}
                    subLabel={tile.unit || undefined}
                  />
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
        <div className="sa-arch-flow" role="list" aria-label="Generated architecture tiers">
          {stackTiers.map((tier, i) => (
            <div key={tier.type} className="sa-arch-flow-item" role="listitem">
              <div className="sa-stat-card-wrap">
                <Tooltip text={tier.help}>
                  <button
                    type="button"
                    className="sa-stat-card-btn"
                    onClick={() => onDrill('components', { type: tier.type })}
                  >
                    <StatCard
                      plain
                      label={tier.label}
                      value={countByType[tier.type] ?? '—'}
                    />
                  </button>
                </Tooltip>
              </div>
              {i < stackTiers.length - 1 && (
                <span className="sa-arch-connector" aria-hidden="true" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
