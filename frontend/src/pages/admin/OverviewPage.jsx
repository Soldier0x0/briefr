import { useState, useEffect } from 'react'
import { adminApi } from '../../api.js'
import StatCard from './shared/StatCard.jsx'
import JobTable from './shared/JobTable.jsx'
import { fmtIso, fmtAge, ageColor, sourceLabel } from './formatters.js'
import { overallHealth, analystScheduleJobs } from './intelStatus.js'
import { jobLabel } from './catalog.js'
import { pauseResumeAction } from './jobActions.js'
import {
  schedulerJobManualRun,
  schedulerJobPaused,
  schedulerJobRefresh,
  schedulerJobResumed,
  schedulerJobRetry,
} from './toastCopy.js'
import OpsCharts from './shared/OpsCharts.jsx'

function AnalystOverview({ system, toast }) {
  const [running, setRunning] = useState({})

  async function runNow(jobId) {
    setRunning(r => ({ ...r, [jobId]: true }))
    try {
      const res = await adminApi.post('/scheduler/run', { job_id: jobId })
      const data = await res.json()
      if (res.status === 409) { toast('Already updating', false); setRunning(r => ({ ...r, [jobId]: false })); return }
      toast(data.ok ? schedulerJobRefresh(jobId, 'analyst') : data.detail, data.ok)
    } catch (e) { toast(String(e.message), false) }
    setTimeout(() => setRunning(r => ({ ...r, [jobId]: false })), 2000)
  }

  const health = overallHealth(system)
  const { db_integrity, scheduler_jobs, active_locks } = system
  const openCircuits = system.open_circuit_count ?? 0
  const sources = system.feeds?.sources || {}
  const worstEntries = Object.entries(sources).filter(([, s]) => s.circuit_open)
  const backupAge = system.last_backup_age_seconds
  const backupThreshold = system.backup_threshold_seconds || 43200
  const showBackupCard = backupAge != null && backupAge > backupThreshold * 0.75

  return (
    <div>
      <h1 className="admin-page-title">Intel status</h1>
      <p className="admin-page-subtitle">Live snapshot — refreshes every 30 seconds.</p>

      <div className={`intel-banner intel-banner-${health.level}`}>
        <strong>{health.headline}</strong>
        <span>{health.detail}</span>
      </div>

      <div className="stat-card-row">
        <StatCard label="CVES IN DATABASE" value={system.cve_count?.toLocaleString()} subLabel="CVEs stored locally" />
        <StatCard
          label="NIST CVE FEED"
          value={fmtAge(system.last_nvd_sync_age_seconds)}
          colorClass={ageColor(system.last_nvd_sync_age_seconds, 7200, 14400)}
          subLabel="usually hourly · incremental"
        />
        {showBackupCard && (
          <StatCard label="LAST BACKUP" value={fmtAge(backupAge)} colorClass="color-amber" subLabel={`threshold ${Math.round(backupThreshold / 3600)}h`} />
        )}
        <StatCard
          label="DATABASE HEALTH"
          value={db_integrity?.ok ? 'Healthy' : 'Problem'}
          colorClass={db_integrity?.ok ? 'color-green' : 'color-red'}
          subLabel="checked on startup"
        />
        <StatCard
          label="SOURCES WITH ISSUES"
          value={openCircuits || 'All OK'}
          colorClass={openCircuits > 0 ? 'color-red' : 'color-green'}
          subLabel={worstEntries.length ? sourceLabel(worstEntries[0][0]) : undefined}
        />
      </div>

      {active_locks?.length > 0 && (
        <div className="admin-card">
          <div className="admin-card-title">Background sync in progress</div>
          {active_locks.map(l => (
            <div key={l.job_id} style={{ fontSize: '0.8125rem', color: 'var(--text2)', padding: '0.2rem 0' }}>
              {jobLabel(l.job_id, 'analyst')} — started recently. Wait before restarting the server.
            </div>
          ))}
        </div>
      )}

      {worstEntries.length > 0 && (
        <div className="admin-card">
          <div className="admin-card-title" style={{ color: 'var(--red)' }}>Problems</div>
          {worstEntries.map(([key]) => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.3rem 0' }}>
              <span style={{ fontSize: '0.8125rem' }}>
                <strong>{sourceLabel(key)}</strong> temporarily unavailable. BRIEFR will retry automatically.
              </span>
              <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem', marginLeft: 'auto' }} onClick={() => adminApi.post(`/feeds/${encodeURIComponent(key)}/reset-circuit`, {}).then(() => toast('Trying again', true)).catch(e => toast(String(e.message), false))}>
                Try again
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="admin-card">
        <div className="admin-card-title">Data refresh schedule</div>
        <JobTable jobs={analystScheduleJobs(scheduler_jobs)} onRunNow={runNow} mode="analyst" />
      </div>
    </div>
  )
}

function OperatorOverview({ system, toast }) {
  const [diagResult, setDiagResult] = useState(null)
  const [intResult, setIntResult] = useState(null)
  const [running, setRunning] = useState({})
  const [showDiag, setShowDiag] = useState(false)
  const [onboarding, setOnboarding] = useState(null)

  useEffect(() => {
    let cancelled = false
    adminApi.get('/onboarding')
      .then(res => res.ok ? res.json() : null)
      .then(data => { if (!cancelled) setOnboarding(data) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  async function dismissOnboarding() {
    setRunning(r => ({ ...r, onboardingDismiss: true }))
    try {
      const res = await adminApi.post('/onboarding/dismiss', {})
      if (res.ok) {
        setOnboarding(prev => prev ? { ...prev, dismissed: true } : prev)
        toast('Checklist dismissed', true)
      }
    } catch (e) { toast(String(e.message), false) }
    setRunning(r => ({ ...r, onboardingDismiss: false }))
  }

  async function runNow(jobId, { retry = false } = {}) {
    setRunning(r => ({ ...r, [jobId]: true }))
    try {
      const res = await adminApi.post('/scheduler/run', { job_id: jobId })
      const data = await res.json()
      if (res.status === 409) { toast('Already running — check active locks', false); setRunning(r => ({ ...r, [jobId]: false })); return }
      toast(
        data.ok
          ? (retry ? schedulerJobRetry(jobId, 'operator') : schedulerJobManualRun(jobId, 'operator'))
          : data.detail,
        data.ok,
      )
    } catch (e) { toast(String(e.message), false) }
    setTimeout(() => setRunning(r => ({ ...r, [jobId]: false })), 2000)
  }

  async function pauseResume(job) {
    const action = pauseResumeAction(job.status)
    if (!action) return
    try {
      const res = await adminApi.post(`/scheduler/${action}`, { job_id: job.id })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || data.ok === false) {
        throw new Error(data.detail || `HTTP ${res.status}`)
      }
      toast(action === 'pause' ? schedulerJobPaused(job.id, 'operator') : schedulerJobResumed(job.id, 'operator'), true)
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

  async function exportSupportPack() {
    setRunning(r => ({ ...r, supportPack: true }))
    try {
      const res = await adminApi.get('/diagnostics/support-pack')
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        toast(data.detail || `Export failed (${res.status})`, false)
        return
      }
      const blob = await res.blob()
      const stamp = new Date().toISOString().replace(/[:.]/g, '').slice(0, 15)
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `briefr-support-pack-${stamp}.json`
      a.click()
      URL.revokeObjectURL(a.href)
      toast('Support pack downloaded', true)
    } catch (e) { toast(String(e.message), false) }
    setRunning(r => ({ ...r, supportPack: false }))
  }

  const { db_integrity, scheduler_jobs, active_locks, recent_errors } = system
  const nvdAgeColorClass = ageColor(system.last_nvd_sync_age_seconds, 7200, 14400)
  const backupAgeColorClass = ageColor(system.last_backup_age_seconds, 28800, 43200)

  return (
    <div>
      <h1 className="admin-page-title">System health</h1>
      <p className="admin-page-subtitle">At-a-glance status: DB integrity, sync ages, active locks, and recent job errors.</p>

      {onboarding && !onboarding.dismissed && !onboarding.complete && (
        <div className="admin-card" style={{ borderColor: 'var(--amber)', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <span className="admin-card-title" style={{ marginBottom: 0 }}>First-hour checklist</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text3)' }}>
              {onboarding.done_count}/{onboarding.total_count} complete
            </span>
            <button
              className="admin-btn admin-btn-ghost"
              style={{ fontSize: '0.7rem', marginLeft: 'auto' }}
              onClick={dismissOnboarding}
              disabled={running.onboardingDismiss}
            >
              Dismiss
            </button>
          </div>
          {onboarding.items.map(item => (
            <div key={item.id} style={{ fontSize: '0.8125rem', display: 'flex', gap: '0.5rem', padding: '0.25rem 0' }}>
              <span style={{ color: item.done ? 'var(--green)' : 'var(--amber)' }}>{item.done ? '✓' : '○'}</span>
              <span style={{ minWidth: 160 }}><strong>{item.title}</strong></span>
              <span style={{ color: 'var(--text3)', flex: 1 }}>{item.detail}</span>
            </div>
          ))}
        </div>
      )}

      <div className="stat-card-row">
        <StatCard label="CVE COUNT" value={system.cve_count?.toLocaleString()} />
        <StatCard label="NVD SYNC AGE" value={fmtAge(system.last_nvd_sync_age_seconds)} colorClass={nvdAgeColorClass} />
        <StatCard label="LAST BACKUP" value={fmtAge(system.last_backup_age_seconds)} colorClass={backupAgeColorClass} />
        <StatCard label="DB INTEGRITY" value={db_integrity?.ok ? 'OK' : 'FAILED'} colorClass={db_integrity?.ok ? 'color-green' : 'color-red'} />
        <StatCard label="TRIPPED CIRCUITS" value={system.open_circuit_count ?? 0} colorClass={system.open_circuit_count > 0 ? 'color-red' : 'color-green'} />
        <StatCard label="JOBS WITH ERRORS" value={system.jobs_with_errors_count ?? 0} colorClass={system.jobs_with_errors_count > 0 ? 'color-red' : 'color-green'} />
      </div>

      <OpsCharts schedulerJobs={scheduler_jobs} />

      <div className="admin-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: showDiag ? '0.75rem' : 0 }}>
          <span className="admin-card-title" style={{ marginBottom: 0 }}>Quick diagnostics</span>
          <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={runSmoke} disabled={running.smoke}>
            {running.smoke ? <><span className="admin-spinner" /> Running…</> : 'Run smoke test'}
          </button>
          <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={runIntegrity} disabled={running.integrity}>
            {running.integrity ? <><span className="admin-spinner" /> Checking…</> : 'Check DB integrity'}
          </button>
          <button
            className="admin-btn admin-btn-ghost"
            style={{ fontSize: '0.75rem' }}
            onClick={exportSupportPack}
            disabled={running.supportPack}
            title="Download redacted health + logs bundle for support (no secrets)"
          >
            {running.supportPack ? <><span className="admin-spinner" /> Exporting…</> : 'Export support pack'}
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
                    <td><button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem' }} onClick={() => runNow(e.job_id, { retry: true })}>Retry</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Scheduler jobs</div>
        <JobTable jobs={scheduler_jobs} onRunNow={runNow} onPauseResume={pauseResume} mode="operator" />
      </div>
    </div>
  )
}

export default function OverviewPage({ system, toast, mode = 'analyst' }) {
  if (!system) return <div className="admin-empty">Loading…</div>
  return mode === 'analyst'
    ? <AnalystOverview system={system} toast={toast} />
    : <OperatorOverview system={system} toast={toast} />
}
