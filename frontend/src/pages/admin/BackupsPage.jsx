import { useState, useEffect, useCallback, useRef } from 'react'
import { adminApi } from '../../api.js'
import StatCard from './shared/StatCard.jsx'
import AsyncSection from './shared/AsyncSection.jsx'
import { fmtBytes, fmtAge, ageColor } from './formatters.js'

export default function BackupsPage({ toast, system, setPage: setAdminPage }) {
  const [backups, setBackups] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [verifyResults, setVerifyResults] = useState({})
  const [page, setPage] = useState(0)
  const [schedule, setSchedule] = useState(null)
  const pageSize = 20
  const fileInputRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const res = await adminApi.get('/backups')
      setBackups(await res.json())
      setLoadError(null)
    } catch (e) {
      setLoadError(e)
    }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    adminApi.get('/config').then(r => r.json()).then(c => setSchedule(c.backup || {})).catch(() => {})
  }, [])

  async function runBackup() {
    setLoading(true)
    try {
      const res = await adminApi.post('/backups/run', {})
      const data = await res.json()
      toast(data.ok ? `Backup created: ${data.filename}` : 'Backup failed', data.ok)
      if (data.ok) load()
    } catch (e) {
      toast(e.status === 409 ? 'Backup already in progress' : String(e.message), false)
    }
    setLoading(false)
  }

  async function verifyBackup(filename) {
    setVerifyResults(r => ({ ...r, [filename]: 'checking' }))
    try {
      const res = await adminApi.post(`/backups/verify/${encodeURIComponent(filename)}`, {})
      const data = await res.json()
      setVerifyResults(r => ({ ...r, [filename]: data }))
      toast(data.ok ? `Verified: ${data.details}` : `Verify failed: ${data.details}`, data.ok)
    } catch (e) {
      setVerifyResults(r => ({ ...r, [filename]: { ok: false, details: String(e.message) } }))
    }
  }

  async function uploadBackup(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await adminApi.postForm('/backups/upload', formData)
      const data = await res.json()
      toast(data.ok ? `Uploaded: ${data.filename}` : 'Upload failed', data.ok)
      if (data.ok) load()
    } catch (e) { toast(String(e.message), false) }
    e.target.value = ''
  }

  const lastBackupAge = system?.last_backup_age_seconds
  const backupAgeColor = ageColor(lastBackupAge, 28800, 43200)
  const archiveCount = backups?.length ?? 0
  const integrityOk = system?.db_integrity?.ok

  const paged = (backups || []).slice(page * pageSize, (page + 1) * pageSize)

  return (
    <div>
      <h1 className="admin-page-title">Backups</h1>
      <p className="admin-page-subtitle">Manages scheduled and on-demand database backups, including restore and integrity checks.</p>

      <div className="stat-card-row">
        <StatCard label="LAST BACKUP" value={fmtAge(lastBackupAge)} colorClass={backupAgeColor} />
        <StatCard label="ARCHIVE COUNT" value={archiveCount} />
        <StatCard label="DB INTEGRITY" value={integrityOk ? 'OK' : 'FAILED'} colorClass={integrityOk ? 'color-green' : 'color-red'} />
      </div>

      {schedule && schedule.BACKUP_INTERVAL_HOURS !== undefined && (
        <div className="admin-card">
          <div className="admin-card-title">Schedule</div>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text2)', marginBottom: '0.5rem' }}>
            {schedule.BACKUP_ENABLED === '0'
              ? 'Scheduled backups are disabled — only manual "Run backup now" creates archives.'
              : `Backups run automatically every ${schedule.BACKUP_INTERVAL_HOURS} hour${schedule.BACKUP_INTERVAL_HOURS === 1 ? '' : 's'}, keeping the latest ${schedule.BACKUP_RETENTION_COUNT} archives (older ones are pruned automatically).`}
          </p>
          {setAdminPage && (
            <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={() => setAdminPage('apikeys')}>
              Edit schedule & retention in Config →
            </button>
          )}
        </div>
      )}

      <div className="admin-action-bar" style={{ justifyContent: 'flex-end' }}>
        <button className="admin-btn admin-btn-primary" onClick={runBackup} disabled={loading}>
          {loading ? <><span className="admin-spinner" /> Running…</> : 'Run backup now'}
        </button>
        <button className="admin-btn admin-btn-ghost" onClick={() => fileInputRef.current?.click()}>
          Upload archive
        </button>
        <input ref={fileInputRef} type="file" accept=".tar.gz,.age" style={{ display: 'none' }} onChange={uploadBackup} />
      </div>

      <div className="admin-card">
        <AsyncSection data={backups} error={loadError} onRetry={load} emptyMessage="No backups found">
          {() => (
            <>
              <table className="admin-table">
                <thead>
                  <tr><th>FILENAME</th><th>SIZE</th><th>AGE</th><th>ENCRYPTED</th><th>INTEGRITY</th><th>REASON</th><th>ACTIONS</th></tr>
                </thead>
                <tbody>
                  {paged.map(b => {
                    const vr = verifyResults[b.filename]
                    return (
                      <tr key={b.filename}>
                        <td className="mono" style={{ fontSize: '0.7rem' }}>{b.filename}</td>
                        <td>{fmtBytes(b.size_bytes)}</td>
                        <td>{fmtAge(b.created_at ? (Date.now() / 1000 - new Date(b.created_at).getTime() / 1000) : null)}</td>
                        <td>{b.encrypted ? <span className="badge badge-info">ENC</span> : <span className="badge badge-muted">plain</span>}</td>
                        <td>
                          {vr && vr !== 'checking' ? (
                            <span className={`badge ${vr.ok ? 'badge-ok' : 'badge-error'}`}>{vr.ok ? 'OK' : 'FAILED'}</span>
                          ) : (
                            <span className={`badge ${b.integrity === 'ok' ? 'badge-ok' : 'badge-warn'}`}>{b.integrity}</span>
                          )}
                        </td>
                        <td style={{ fontSize: '0.75rem' }}>{b.reason || '—'}</td>
                        <td>
                          <button
                            className="admin-btn admin-btn-ghost"
                            style={{ fontSize: '0.7rem', padding: '0.15rem 0.4rem' }}
                            onClick={() => verifyBackup(b.filename)}
                            disabled={vr === 'checking'}
                          >
                            {vr === 'checking' ? <span className="admin-spinner" /> : 'Verify'}
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {(backups || []).length > pageSize && (
                <div className="admin-pagination">
                  <button className="admin-btn admin-btn-ghost" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
                  <span style={{ color: 'var(--text3)', fontSize: '0.8125rem' }}>
                    {page * pageSize + 1}–{Math.min((page + 1) * pageSize, backups.length)} of {backups.length}
                  </span>
                  <button className="admin-btn admin-btn-ghost" disabled={(page + 1) * pageSize >= backups.length} onClick={() => setPage(p => p + 1)}>Next →</button>
                </div>
              )}
            </>
          )}
        </AsyncSection>
      </div>

      <div className="admin-callout admin-callout-amber" style={{ marginTop: '1rem' }}>
        <strong>Restore is a CLI operation</strong> to prevent accidental data loss.<br />
        <code className="mono">bash /opt/briefr/deploy/briefr-restore.sh</code><br />
        To restore specific archive: <code className="mono">briefr-restore.sh {'<filename>'}</code>
      </div>
    </div>
  )
}
