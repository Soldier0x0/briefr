import { useEffect, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { adminApi } from '../../api.js'
import StatCard from './shared/StatCard.jsx'
import DbExplorerPanel from './DbExplorerPanel.jsx'
import IntelSnapshotPanel from './IntelSnapshotPanel.jsx'
import { fmtBytes } from './formatters.js'

export default function DatabasePage({ toast, active = true }) {
  const [info, setInfo] = useState(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await adminApi.get('/database')
        const data = await res.json()
        if (!cancelled) setInfo(data)
      } catch (err) {
        toast(String(err.message || err), false)
      }
    })()
    return () => { cancelled = true }
  }, [toast])

  if (!info) {
    return (
      <div>
        <h1 className="admin-page-title">Database</h1>
        <p className="admin-page-subtitle">Loading database configuration…</p>
      </div>
    )
  }

  return (
    <div>
      <h1 className="admin-page-title">Database</h1>
      <p className="admin-page-subtitle">
        PostgreSQL 16 + pgvector via <code>DATABASE_URL</code>. See <code>docs/POSTGRES.md</code>.
      </p>

      <div className="stat-card-row">
        <StatCard label="ENGINE" value="PostgreSQL" colorClass="color-green" />
        {info.postgres_dsn_redacted && (
          <StatCard label="TARGET" value={info.postgres_dsn_redacted} />
        )}
      </div>

      {info.metrics && (
        <>
          {info.metrics.disk_projection?.severity && info.metrics.disk_projection.severity !== 'ok' && (
            <div className={`intel-banner intel-banner-${info.metrics.disk_projection.severity === 'critical' ? 'red' : 'amber'}`} role="status">
              <span>
                Disk projection: {info.metrics.disk_projection.daily_growth_bytes != null
                  ? `${fmtBytes(info.metrics.disk_projection.daily_growth_bytes)}/day growth`
                  : 'insufficient samples'}
                {info.metrics.disk_projection.projected_bytes != null && (
                  <> — projected {fmtBytes(info.metrics.disk_projection.projected_bytes)} in 30 days</>
                )}
                {info.metrics.disk_projection.pct_of_partition != null && (
                  <> ({info.metrics.disk_projection.pct_of_partition}% of partition)</>
                )}
              </span>
            </div>
          )}
          <div className="stat-card-row admin-database-metrics-grid">
            <StatCard label="DB SIZE" value={fmtBytes(info.metrics.db_size_bytes)} />
            <StatCard label="CONNECTIONS" value={String(info.metrics.connections ?? '—')} />
            <StatCard
              label="CACHE HIT"
              value={info.metrics.cache_hit_ratio != null ? `${info.metrics.cache_hit_ratio}%` : '—'}
            />
            <StatCard label="TABLES" value={String(info.metrics.table_count ?? '—')} />
            <StatCard label="INDEXES" value={String(info.metrics.index_count ?? '—')} />
            <StatCard
              label="INTEGRITY"
              value={info.metrics.integrity_ok ? 'OK' : 'FAILED'}
              colorClass={info.metrics.integrity_ok ? 'color-green' : 'color-red'}
              subLabel={info.metrics.integrity_checked_at ? String(info.metrics.integrity_checked_at).slice(0, 19) : null}
            />
          </div>
        </>
      )}

      <div className="admin-callout admin-callout-amber">
        <AlertTriangle size={16} strokeWidth={2} />
        <span>
          Running on PostgreSQL. Backups use <code>pg_dump</code> (<code>briefr.pgdump</code> in each archive).
          Restore via <code>deploy/briefr-restore.sh</code> — see <code>docs/POSTGRES.md</code>.
        </span>
      </div>

      <IntelSnapshotPanel toast={toast} />
      <DbExplorerPanel toast={toast} active={active} />
    </div>
  )
}
