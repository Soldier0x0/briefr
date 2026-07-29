import { useState, useEffect, useRef } from 'react'
import { AlertTriangle } from 'lucide-react'
import { adminApi } from '../../api.js'
import { notifyBackendRestarting } from '../../utils/backendRestart.js'
import ConfirmModal from './shared/ConfirmModal.jsx'
import DangerZone from './shared/DangerZone.jsx'
import StatCard from './shared/StatCard.jsx'
import DbExplorerPanel from './DbExplorerPanel.jsx'
import IntelSnapshotPanel from './IntelSnapshotPanel.jsx'
import { fmtBytes } from './formatters.js'

// PostgreSQL connection: test target DSN, copy data into Postgres, apply DATABASE_URL + restart.
export default function DatabasePage({ toast, active = true }) {
  const [info, setInfo] = useState(null)
  const [databaseUrl, setDatabaseUrl] = useState('')
  const [testResult, setTestResult] = useState(null)
  const [testing, setTesting] = useState(false)
  const [confirmMigrate, setConfirmMigrate] = useState(false)
  const [status, setStatus] = useState(null)
  const [applying, setApplying] = useState(false)
  const pollRef = useRef(null)

  async function loadInfo() {
    try {
      const res = await adminApi.get('/database')
      setInfo(await res.json())
    } catch { }
  }

  async function loadStatus() {
    try {
      const res = await adminApi.get('/database/migrate/status')
      const data = await res.json()
      setStatus(data)
      return data
    } catch { return null }
  }

  useEffect(() => { loadInfo(); loadStatus() }, [])

  useEffect(() => {
    if (status?.status === 'running' && active) {
      pollRef.current = setInterval(loadStatus, 2000)
    } else {
      clearInterval(pollRef.current)
    }
    return () => clearInterval(pollRef.current)
  }, [status?.status, active])

  async function testConnection() {
    if (!databaseUrl.trim()) { toast('Enter a postgresql:// URL first', false); return }
    setTesting(true)
    setTestResult(null)
    try {
      const res = await adminApi.post('/database/test-connection', { database_url: databaseUrl })
      const data = await res.json()
      setTestResult(data)
      toast(data.ok ? 'Connection OK' : `Failed: ${data.error}`, data.ok)
    } catch (e) { toast(String(e.message), false) }
    setTesting(false)
  }

  async function startMigration() {
    setConfirmMigrate(false)
    try {
      const res = await adminApi.post('/database/migrate', { database_url: databaseUrl, confirm_text: 'migrate' })
      const data = await res.json()
      if (res.status === 409) { toast('A migration is already running', false); return }
      toast(data.ok ? 'Migration started' : data.detail || 'Failed to start', data.ok)
      loadStatus()
    } catch (e) { toast(String(e.message), false) }
  }

  async function applyAndRestart() {
    setApplying(true)
    try {
      const res = await adminApi.post('/config/apply-all', [{ key: 'DATABASE_URL', value: databaseUrl }])
      const data = await res.json()
      if (data.ok) notifyBackendRestarting()
      toast(data.ok ? 'DATABASE_URL applied' : data.detail || 'Failed', data.ok)
    } catch (e) { toast(String(e.message), false) }
    setApplying(false)
  }

  const progressPct = status?.tables_total
    ? Math.round((status.tables_done / status.tables_total) * 100)
    : 0

  if (!info) {
    return (
      <div>
        <h1 className="admin-page-title">Database</h1>
        <p className="admin-page-subtitle">Loading database configuration…</p>
      </div>
    )
  }

  const needsPostgres = info.engine !== 'postgresql'
  const migrationDone = status?.status === 'done'
  const migrationRunning = status?.status === 'running'
  const migrationError = status?.status === 'error'

  return (
    <div>
      {confirmMigrate && (
        <ConfirmModal
          title="Start PostgreSQL data copy?"
          message="Copies every row from the current database into the target PostgreSQL database, replacing any existing data there. Take a backup first (Backups page). A bad target URL could leave the target empty — verify the connection before running. This is safely re-runnable if it fails partway."
          confirmWord="migrate"
          onConfirm={startMigration}
          onCancel={() => setConfirmMigrate(false)}
        />
      )}

      <h1 className="admin-page-title">Database</h1>
      <p className="admin-page-subtitle">PostgreSQL connection, health, and read-only table browser. Production uses Postgres 16+ via <code>DATABASE_URL</code>; see <code>docs/POSTGRES.md</code>.</p>

      <div className="stat-card-row">
        <StatCard label="ENGINE" value={info?.engine === 'postgresql' ? 'PostgreSQL' : 'Not connected'} colorClass={needsPostgres ? 'color-amber' : 'color-green'} />
        {needsPostgres && info?.sqlite_size_bytes != null && (
          <StatCard label="LOCAL DATA SIZE" value={fmtBytes(info.sqlite_size_bytes)} />
        )}
        {!needsPostgres && info && <StatCard label="TARGET" value={info.postgres_dsn_redacted} />}
      </div>

      {info?.metrics && (
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
            {info.metrics.wal_size_bytes > 0 && (
              <StatCard label="WAL SIZE" value={fmtBytes(info.metrics.wal_size_bytes)} />
            )}
          </div>
        </>
      )}

      {info?.require_postgres && needsPostgres && (
        <div className="admin-callout admin-callout-amber" style={{ marginBottom: '1rem' }}>
          <AlertTriangle size={16} strokeWidth={2} />
          <span>
            <strong>PostgreSQL required</strong> — <code>BRIEFR_REQUIRE_POSTGRES=1</code> is set.
            Set <code>DATABASE_URL</code> below and complete the data copy before the backend will start.
          </span>
        </div>
      )}

      {needsPostgres ? (
        <>
          <div className="admin-callout admin-callout-amber">
            <AlertTriangle size={16} strokeWidth={2} />
            <span>
              Backend is not on PostgreSQL yet. Point <code>DATABASE_URL</code> at your Postgres instance
              (production: Docker at <code>/opt/infra/postgres</code>, port <code>5432</code>) — see <code>docs/POSTGRES.md</code>.
            </span>
          </div>

          <DangerZone title="Connect PostgreSQL">
            <div style={{ fontSize: '0.8125rem', color: 'var(--text2)', marginBottom: '0.75rem' }}>
              1. Take a backup. 2. Test the connection below. 3. Run the data copy. 4. Apply &amp; restart once it finishes.
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
              <input
                className="admin-input"
                style={{ minWidth: 360, fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}
                placeholder="postgresql://briefr:briefr@127.0.0.1:5432/briefr"
                value={databaseUrl}
                onChange={e => { setDatabaseUrl(e.target.value); setTestResult(null) }}
              />
              <button className="admin-btn admin-btn-ghost" onClick={testConnection} disabled={testing}>
                {testing ? <><span className="admin-spinner" /> Testing…</> : 'Test connection'}
              </button>
            </div>
            {testResult && (
              <div style={{ fontSize: '0.8rem', color: testResult.ok ? 'var(--green)' : 'var(--red)', marginBottom: '0.5rem' }}>
                {testResult.ok ? `✓ Connected (${testResult.server_version?.slice(0, 60)})` : `✗ ${testResult.error}`}
              </div>
            )}

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                className="admin-btn admin-btn-danger"
                onClick={() => setConfirmMigrate(true)}
                disabled={!testResult?.ok || migrationRunning}
              >
                Run data copy
              </button>
            </div>

            {status && status.status !== 'idle' && (
              <div style={{ marginTop: '1rem' }}>
                {migrationRunning && (
                  <>
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text2)', marginBottom: '0.35rem' }}>
                      Copying {status.current_table || '…'} — {status.tables_done}/{status.tables_total} tables, {status.rows_copied?.toLocaleString()} rows copied
                    </div>
                    <div className="disk-bar">
                      <div className="disk-bar-fill disk-bar-fill-green" style={{ width: `${progressPct}%` }} />
                    </div>
                  </>
                )}
                {migrationDone && (
                  <div className="admin-callout admin-callout-amber">
                    <AlertTriangle size={16} strokeWidth={2} />
                    <span>
                      <strong>Data copy complete</strong> — {status.rows_copied?.toLocaleString()} rows copied across {status.tables_total} tables.
                      {status.verification?.mismatches?.length > 0 && (
                        <span style={{ display: 'block', marginTop: '0.35rem', color: 'var(--red)' }}>
                          Row-count mismatches: {status.verification.mismatches.join(', ')} — review before switching.
                        </span>
                      )}
                      {status.verification?.mismatches?.length === 0 && status.verification?.tables && (
                        <span style={{ display: 'block', marginTop: '0.35rem', color: 'var(--green)' }}>
                          Row counts verified for all copied tables.
                        </span>
                      )}
                      Verify the data looks right against the target database, then apply the switch:
                      <div style={{ marginTop: '0.5rem' }}>
                        <button className="admin-btn admin-btn-primary" onClick={applyAndRestart} disabled={applying}>
                          {applying ? <><span className="admin-spinner" /> Applying…</> : 'Apply DATABASE_URL & restart'}
                        </button>
                      </div>
                    </span>
                  </div>
                )}
                {migrationError && (
                  <div style={{ fontSize: '0.8125rem', color: 'var(--red)' }}>
                    Data copy failed: {status.error}
                  </div>
                )}
              </div>
            )}
          </DangerZone>
        </>
      ) : (
        <div className="admin-callout admin-callout-amber">
          <AlertTriangle size={16} strokeWidth={2} />
          <span>
            Running on PostgreSQL. Backups use <code>pg_dump</code> (<code>briefr.pgdump</code> in each archive).
            Restore via <code>deploy/briefr-restore.sh</code> — see <code>docs/POSTGRES.md</code>.
          </span>
        </div>
      )}

      {!needsPostgres && (
        <IntelSnapshotPanel toast={toast} />
      )}

      <DbExplorerPanel toast={toast} active={active} />
    </div>
  )
}
