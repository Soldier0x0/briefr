import { useState } from 'react'
import { adminApi } from '../../api.js'
import StatCard from './shared/StatCard.jsx'
import JobTable from './shared/JobTable.jsx'
import { fmtIso, fmtAge, ageColor } from './formatters.js'

export default function OverviewPage({ system, toast }) {
  const [diagResult, setDiagResult] = useState(null)
  const [intResult, setIntResult] = useState(null)
  const [running, setRunning] = useState({})
  const [showDiag, setShowDiag] = useState(false)

  async function runNow(jobId) {
    setRunning(r => ({ ...r, [jobId]: true }))
    try {
      const res = await adminApi.post('/scheduler/run', { job_id: jobId })
      const data = await res.json()
      if (res.status === 409) { toast('Already running — check active locks', false); return }
      toast(data.ok ? `Job started: ${jobId}` : data.detail, data.ok)
    } catch (e) { toast(String(e.message), false) }
    setTimeout(() => setRunning(r => ({ ...r, [jobId]: false })), 2000)
  }

  async function pauseResume(job) {
    const action = job.status === 'PAUSED' ? 'resume' : 'pause'
    try {
      const res = await adminApi.post(`/scheduler/${action}`, { job_id: job.id })
      const data = await res.json()
      toast(data.ok ? `Job ${action}d` : 'Failed', data.ok)
    } catch (e) { toast(String(e.message), false) }
  }

  async function runSmoke() {
    setRunning(r => ({ ...r, smoke: true }))
    try {
      const res = await adminApi.post('/diagnostics/smoke', {})
      const data = await res.json()
      setDiagResult(data)
      setShowDiag(true)
    } catch (e) { toast(String(e.message), false) }
    setRunning(r => ({ ...r, smoke: false }))
  }

  async function runIntegrity() {
    setRunning(r => ({ ...r, integrity: true }))
    try {
      const res = await adminApi.post('/diagnostics/integrity', {})
      const data = await res.json()
      setIntResult(data)
      setShowDiag(true)
    } catch (e) { toast(String(e.message), false) }
    setRunning(r => ({ ...r, integrity: false }))
  }

  if (!system) return <div className="admin-empty">Loading…</div>

  const { db_integrity, scheduler_jobs, active_locks, recent_errors } = system
  const nvdAgeColor = ageColor(system.last_nvd_sync_age_seconds, 7200, 14400)
  const backupAgeColor = ageColor(system.last_backup_age_seconds, 28800, 43200)

  return (
    <div>
      <h1 className="admin-page-title">System health</h1>

      {/* Stat cards */}
      <div className="stat-card-row">
        <StatCard label="CVE COUNT" value={system.cve_count?.toLocaleString()} />
        <StatCard label="NVD SYNC AGE" value={fmtAge(system.last_nvd_sync_age_seconds)} colorClass={nvdAgeColor} />
        <StatCard label="LAST BACKUP" value={fmtAge(system.last_backup_age_seconds)} colorClass={backupAgeColor} />
        <StatCard label="DB INTEGRITY" value={db_integrity?.ok ? 'OK' : 'FAILED'} colorClass={db_integrity?.ok ? 'color-green' : 'color-red'} />
        <StatCard label="OPEN CIRCUITS" value={system.open_circuit_count ?? 0} colorClass={system.open_circuit_count > 0 ? 'color-red' : 'color-green'} />
        <StatCard label="JOBS WITH ERRORS" value={system.jobs_with_errors_count ?? 0} colorClass={system.jobs_with_errors_count > 0 ? 'color-red' : 'color-green'} />
      </div>

      {/* Quick diagnostics */}
      <div className="admin-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: showDiag ? '0.75rem' : 0 }}>
          <span className="admin-card-title" style={{ marginBottom: 0 }}>Quick diagnostics</span>
          <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={runSmoke} disabled={running.smoke}>
            {running.smoke ? <><span className="admin-spinner" /> Running…</> : 'Run smoke test'}
          </button>
          <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={runIntegrity} disabled={running.integrity}>
            {running.integrity ? <><span className="admin-spinner" /> Checking…</> : 'Check DB integrity'}
          </button>
          {showDiag && <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.7rem' }} onClick={() => setShowDiag(false)}>Hide</button>}
        </div>
        {showDiag && diagResult && (
          <div style={{ marginTop: '0.5rem' }}>
            <div style={{ marginBottom: '0.25rem', fontSize: '0.75rem', color: diagResult.ok ? 'var(--green)' : 'var(--red)' }}>
              {diagResult.ok ? '✓ All checks passed' : '✗ Some checks failed'} ({diagResult.duration_ms}ms)
            </div>
            {diagResult.checks?.map((c, i) => (
              <div key={i} style={{ fontSize: '0.8125rem', display: 'flex', gap: '0.5rem', padding: '0.2rem 0' }}>
                <span style={{ color: c.passed ? 'var(--green)' : 'var(--red)' }}>{c.passed ? '✓' : '✗'}</span>
                <span>{c.name}</span>
                <span style={{ color: 'var(--text3)' }}>{c.detail}</span>
              </div>
            ))}
          </div>
        )}
        {showDiag && intResult && (
          <div style={{ marginTop: '0.5rem', fontSize: '0.8125rem' }}>
            <span style={{ color: intResult.integrity_ok ? 'var(--green)' : 'var(--red)' }}>
              {intResult.integrity_ok ? '✓ Integrity OK' : '✗ Integrity FAILED'}
            </span>
            {' — '}
            <span style={{ color: intResult.foreign_keys_ok ? 'var(--green)' : 'var(--red)' }}>
              {intResult.foreign_keys_ok ? '✓ FK OK' : `✗ ${intResult.foreign_key_violations} FK violations`}
            </span>
          </div>
        )}
      </div>

      {/* Two-column: active locks + recent errors */}
      <div className="admin-two-col">
        <div className="admin-card" style={{ flex: 1 }}>
          <div className="admin-card-title">Active locks</div>
          {(!active_locks || active_locks.length === 0) ? (
            <div className="admin-empty">No jobs running</div>
          ) : (
            <table className="admin-table">
              <thead><tr><th>JOB ID</th><th>LOCK</th></tr></thead>
              <tbody>
                {active_locks.map(l => (
                  <tr key={l.job_id}>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{l.job_id}</td>
                    <td><span className="badge badge-info">LOCKED</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="admin-card" style={{ flex: 1 }}>
          <div className="admin-card-title">Recent errors</div>
          {(!recent_errors || recent_errors.length === 0) ? (
            <div className="admin-empty" style={{ color: 'var(--green)' }}>All jobs clean</div>
          ) : (
            <table className="admin-table">
              <thead><tr><th>JOB ID</th><th>ERROR</th><th>LAST RUN</th><th></th></tr></thead>
              <tbody>
                {recent_errors.map(e => (
                  <tr key={e.job_id}>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{e.job_id}</td>
                    <td style={{ fontSize: '0.75rem', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.error || '—'}</td>
                    <td style={{ fontSize: '0.75rem' }}>{fmtIso(e.last_run_utc)}</td>
                    <td><button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem' }} onClick={() => runNow(e.job_id)}>Retry</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Full scheduler table */}
      <div className="admin-card">
        <div className="admin-card-title">Scheduler jobs</div>
        <JobTable jobs={scheduler_jobs} onRunNow={runNow} onPauseResume={pauseResume} />
      </div>
    </div>
  )
}
