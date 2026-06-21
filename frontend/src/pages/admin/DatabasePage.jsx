import { useState, useEffect, useRef } from 'react'
import { AlertTriangle } from 'lucide-react'
import { adminApi } from '../../api.js'
import ConfirmModal from './shared/ConfirmModal.jsx'
import DangerZone from './shared/DangerZone.jsx'
import StatCard from './shared/StatCard.jsx'
import { fmtBytes } from './formatters.js'

// Lets a single operator move from the default SQLite file to an optional
// PostgreSQL database without leaving the admin panel: test the target
// connection, run a one-shot data copy (reusing the existing Alembic schema
// + the SQLite file already on disk), then flip DATABASE_URL through the
// same apply-all + graceful-restart flow used elsewhere in this panel.
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
      toast(data.ok ? 'DATABASE_URL applied — backend restarting onto PostgreSQL' : data.detail || 'Failed', data.ok)
    } catch (e) { toast(String(e.message), false) }
    setApplying(false)
  }

  const isSqlite = info?.engine === 'sqlite'
  const migrationDone = status?.status === 'done'
  const migrationRunning = status?.status === 'running'
  const migrationError = status?.status === 'error'
  const progressPct = status?.tables_total
    ? Math.round((status.tables_done / status.tables_total) * 100)
    : 0

  return (
    <div>
      {confirmMigrate && (
        <ConfirmModal
          title="Start PostgreSQL migration?"
          message="Copies every row from the current SQLite database into the target PostgreSQL database, replacing any existing data there. Take a backup first (Backups page) — this does not touch the SQLite file, but a bad target URL could otherwise leave you without a path back. This is safely re-runnable if it fails partway."
          confirmWord="migrate"
          onConfirm={startMigration}
          onCancel={() => setConfirmMigrate(false)}
        />
      )}

      <h1 className="admin-page-title">Database</h1>
      <p className="admin-page-subtitle">Shows the current database engine and lets you migrate from SQLite to PostgreSQL. The migration is one-way and triggers a restart.</p>

      <div className="stat-card-row">
        <StatCard label="ENGINE" value={info?.engine === 'postgresql' ? 'PostgreSQL' : 'SQLite'} colorClass={isSqlite ? 'color-amber' : 'color-green'} />
        {isSqlite && info && <StatCard label="SQLITE FILE SIZE" value={fmtBytes(info.sqlite_size_bytes)} />}
        {!isSqlite && info && <StatCard label="TARGET" value={info.postgres_dsn_redacted} />}
      </div>

      {isSqlite ? (
        <>
          <div className="admin-callout admin-callout-amber">
            <AlertTriangle size={16} strokeWidth={2} />
            <span>
              Running on SQLite (single-writer). PostgreSQL is optional and only worth migrating to if you need
              concurrent writers or multiple uvicorn workers — see <code>docs/POSTGRES.md</code>.
            </span>
          </div>

          <DangerZone title="Migrate to PostgreSQL">
            <div style={{ fontSize: '0.8125rem', color: 'var(--text2)', marginBottom: '0.75rem' }}>
              1. Take a backup. 2. Test the connection below. 3. Run the migration. 4. Apply &amp; restart once it finishes.
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
                Run migration
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
                      <strong>Migration complete</strong> — {status.rows_copied?.toLocaleString()} rows copied across {status.tables_total} tables.
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
                    Migration failed: {status.error}
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
            Running on PostgreSQL. To roll back to SQLite: stop the backend, restore a pre-migration SQLite backup,
            remove <code>DATABASE_URL</code>, and restart — see <code>docs/POSTGRES.md</code>.
          </span>
        </div>
      )}
    </div>
  )
}
