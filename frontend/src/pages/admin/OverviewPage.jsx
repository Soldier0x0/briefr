import { useState } from 'react'
import { adminApi } from '../../api.js'
import StatCard from './shared/StatCard.jsx'
import JobTable from './shared/JobTable.jsx'
import JobErrorsPanel from './shared/JobErrorsPanel.jsx'
import ActionProgress from './shared/ActionProgress.jsx'
import { fmtAge, ageColor, sourceLabel } from './formatters.js'
import { overallHealth, analystScheduleJobs, nvdCadenceLabel } from './intelStatus.js'
import { jobLabel } from './catalog.js'
import { getRunningJobs, getSchedulerJobs } from './jobStatus.js'
import RunningJobsPanel from './shared/RunningJobsPanel.jsx'

function AnalystOverview({ system, toast, jobAcks, onMarkJobErrorsRead }) {
  const [running, setRunning] = useState({})
  const [progress, setProgress] = useState(null)

  async function runNow(jobId) {
    setRunning(r => ({ ...r, [jobId]: true }))
    setProgress({ label: `Starting ${jobLabel(jobId, 'analyst')}…`, stage: 'Contacting scheduler' })
    try {
      const res = await adminApi.post('/scheduler/run', { job_id: jobId })
      const data = await res.json()
      if (res.status === 409) {
        toast('Already updating', false)
        setProgress(null)
        setRunning(r => ({ ...r, [jobId]: false }))
        return
      }
      setProgress({ label: data.ok ? 'Job started' : 'Job failed to start', stage: data.detail || jobId })
      toast(data.ok ? `${jobLabel(jobId, 'analyst')} refresh started` : data.detail, data.ok)
    } catch (e) {
      toast(String(e.message), false)
      setProgress({ label: 'Request failed', stage: String(e.message) })
    }
    setTimeout(() => {
      setRunning(r => ({ ...r, [jobId]: false }))
      setProgress(null)
    }, 2500)
  }

  const health = overallHealth(system)
  const { db_integrity, scheduler_jobs } = system
  const normalizedJobs = getSchedulerJobs(system, scheduler_jobs)
  const runningJobs = getRunningJobs(system, scheduler_jobs)
  const openCircuits = system.open_circuit_count ?? 0
  const sources = system.feeds?.sources || {}
  const worstEntries = Object.entries(sources).filter(([, s]) => s.circuit_open)
  const backupAge = system.last_backup_age_seconds
  const backupThreshold = system.backup_threshold_seconds || 43200
  const showBackupCard = backupAge != null && backupAge > backupThreshold * 0.75

  return (
    <div>
      <header className="admin-page-header">
        <h1 className="admin-page-title">Intel status</h1>
        <p className="admin-page-subtitle">Live snapshot of CVE data freshness and upstream feed health.</p>
      </header>

      <div className={`intel-banner intel-banner-${health.level}`}>
        <strong>{health.headline}</strong>
        <span>{health.detail}</span>
      </div>
      {health.issues?.length > 1 && (
        <ul className="intel-issue-list">
          {health.issues.map((issue, i) => (
            <li key={i}>{issue}</li>
          ))}
        </ul>
      )}

      <ActionProgress label={progress?.label} stage={progress?.stage} visible={!!progress} />

      <div className="stat-card-row admin-stat-grid">
        <StatCard label="CVEs in database" value={system.cve_count?.toLocaleString()} subLabel="Stored locally" />
        <StatCard
          label="NIST CVE feed"
          value={fmtAge(system.last_nvd_sync_age_seconds)}
          colorClass={ageColor(system.last_nvd_sync_age_seconds, 7200, 14400)}
          subLabel={nvdCadenceLabel(system)}
        />
        {showBackupCard && (
          <StatCard label="Last backup" value={fmtAge(backupAge)} colorClass="color-amber" subLabel={`threshold ${Math.round(backupThreshold / 3600)}h`} />
        )}
        <StatCard
          label="Database health"
          value={db_integrity?.ok ? 'Healthy' : 'Problem'}
          colorClass={db_integrity?.ok ? 'color-green' : 'color-red'}
          subLabel="Checked on startup"
        />
        <StatCard
          label="Sources with issues"
          value={openCircuits || 'All OK'}
          colorClass={openCircuits > 0 ? 'color-red' : 'color-green'}
          subLabel={worstEntries.length ? sourceLabel(worstEntries[0][0]) : undefined}
        />
      </div>

      {runningJobs.length > 0 && (
        <div className="admin-card admin-section-gap">
          <div className="admin-card-title">Background sync in progress</div>
          <RunningJobsPanel jobs={runningJobs} mode="analyst" />
        </div>
      )}

      <JobErrorsPanel
        system={system}
        jobAcks={jobAcks}
        onMarkAllRead={onMarkJobErrorsRead}
        onRetry={runNow}
        mode="analyst"
        running={running}
      />

      {worstEntries.length > 0 && (
        <div className="admin-card admin-section-gap">
          <div className="admin-card-title" style={{ color: 'var(--red)' }}>Feed circuit problems</div>
          {worstEntries.map(([key]) => (
            <div key={key} className="admin-purge-row" style={{ marginTop: 8, border: 'none', padding: '8px 0' }}>
              <div className="admin-purge-row-info">
                <div className="admin-purge-row-title">{sourceLabel(key)}</div>
                <div className="admin-purge-row-desc">Temporarily unavailable — BRIEFR will retry automatically.</div>
              </div>
              <button
                type="button"
                className="admin-btn admin-btn-ghost admin-btn--sm"
                onClick={() => adminApi.post(`/feeds/${encodeURIComponent(key)}/reset-circuit`, {}).then(() => toast('Trying again', true)).catch(e => toast(String(e.message), false))}
              >
                Try again
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="admin-card admin-section-gap">
        <div className="admin-card-title">Data refresh schedule</div>
        <div className="admin-table-wrap">
          <JobTable jobs={analystScheduleJobs(normalizedJobs)} onRunNow={runNow} mode="analyst" />
        </div>
      </div>
    </div>
  )
}

const OPERATOR_TABS = [
  { id: 'health', label: 'Health' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'diagnostics', label: 'Diagnostics' },
]

function OperatorOverview({ system, toast, jobAcks, onMarkJobErrorsRead }) {
  const [tab, setTab] = useState('health')
  const [diagResult, setDiagResult] = useState(null)
  const [intResult, setIntResult] = useState(null)
  const [running, setRunning] = useState({})
  const [progress, setProgress] = useState(null)

  async function runNow(jobId) {
    setRunning(r => ({ ...r, [jobId]: true }))
    setProgress({ label: `Starting ${jobLabel(jobId, 'operator')}…`, stage: 'Contacting scheduler' })
    try {
      const res = await adminApi.post('/scheduler/run', { job_id: jobId })
      const data = await res.json()
      if (res.status === 409) {
        toast('Already running — check active locks', false)
        setProgress(null)
        setRunning(r => ({ ...r, [jobId]: false }))
        return
      }
      toast(data.ok ? `Job started: ${jobLabel(jobId, 'operator')}` : data.detail, data.ok)
      setProgress({ label: data.ok ? 'Job started' : 'Failed', stage: data.detail || '' })
    } catch (e) {
      toast(String(e.message), false)
      setProgress({ label: 'Request failed', stage: String(e.message) })
    }
    setTimeout(() => {
      setRunning(r => ({ ...r, [jobId]: false }))
      setProgress(null)
    }, 2500)
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
    setProgress({ label: 'Running smoke test…', stage: 'Checking core endpoints' })
    try {
      const res = await adminApi.post('/diagnostics/smoke', {})
      setDiagResult(await res.json())
      setTab('diagnostics')
    } catch (e) { toast(String(e.message), false) }
    setRunning(r => ({ ...r, smoke: false }))
    setProgress(null)
  }

  async function runIntegrity() {
    setRunning(r => ({ ...r, integrity: true }))
    setProgress({ label: 'Checking database integrity…', stage: 'Running PRAGMA checks' })
    try {
      const res = await adminApi.post('/diagnostics/integrity', {})
      setIntResult(await res.json())
      setTab('diagnostics')
    } catch (e) { toast(String(e.message), false) }
    setRunning(r => ({ ...r, integrity: false }))
    setProgress(null)
  }

  const { db_integrity, scheduler_jobs } = system
  const normalizedJobs = getSchedulerJobs(system, scheduler_jobs)
  const runningJobs = getRunningJobs(system, scheduler_jobs)

  return (
    <div>
      <header className="admin-page-header">
        <h1 className="admin-page-title">System health</h1>
        <p className="admin-page-subtitle">Database integrity, sync ages, scheduler locks, and job errors.</p>
      </header>

      <div className="admin-subtabs" role="tablist" aria-label="Operator overview sections">
        {OPERATOR_TABS.map(t => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`admin-subtab ${tab === t.id ? 'admin-subtab--active active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <ActionProgress label={progress?.label} stage={progress?.stage} visible={!!progress} />

      {tab === 'health' && (
        <>
          <div className="stat-card-row admin-stat-grid">
            <StatCard label="CVE count" value={system.cve_count?.toLocaleString()} />
            <StatCard label="NVD sync age" value={fmtAge(system.last_nvd_sync_age_seconds)} colorClass={ageColor(system.last_nvd_sync_age_seconds, 7200, 14400)} subLabel={nvdCadenceLabel(system)} />
            <StatCard label="Last backup" value={fmtAge(system.last_backup_age_seconds)} colorClass={ageColor(system.last_backup_age_seconds, 28800, 43200)} />
            <StatCard label="DB integrity" value={db_integrity?.ok ? 'OK' : 'FAILED'} colorClass={db_integrity?.ok ? 'color-green' : 'color-red'} />
            <StatCard label="Open circuits" value={system.open_circuit_count ?? 0} colorClass={system.open_circuit_count > 0 ? 'color-red' : 'color-green'} />
            <StatCard label="Jobs with errors" value={system.jobs_with_errors_count ?? 0} colorClass={system.jobs_with_errors_count > 0 ? 'color-red' : 'color-green'} />
          </div>

          <div className="admin-card">
            <div className="admin-card-header">
              <h2 className="admin-card-title">Quick diagnostics</h2>
              <div className="admin-btn-row" style={{ marginTop: 0 }}>
                <button type="button" className="admin-btn admin-btn-ghost admin-btn--sm" onClick={runSmoke} disabled={running.smoke}>
                  {running.smoke ? <><span className="admin-spinner" /> Running…</> : 'Run smoke test'}
                </button>
                <button type="button" className="admin-btn admin-btn-ghost admin-btn--sm" onClick={runIntegrity} disabled={running.integrity}>
                  {running.integrity ? <><span className="admin-spinner" /> Checking…</> : 'Check DB integrity'}
                </button>
              </div>
            </div>
            <div className="admin-card-body admin-text-muted" style={{ fontSize: 12 }}>
              Smoke test hits core API endpoints; integrity check runs database PRAGMA validation.
            </div>
          </div>
        </>
      )}

      {tab === 'jobs' && (
        <>
          <div className="admin-card admin-section-gap">
            <div className="admin-card-title">Active locks</div>
            <RunningJobsPanel jobs={runningJobs} mode="operator" showTechnicalIds />
          </div>

          <JobErrorsPanel
            system={system}
            jobAcks={jobAcks}
            onMarkAllRead={onMarkJobErrorsRead}
            onRetry={runNow}
            mode="operator"
            running={running}
          />

          <div className="admin-card admin-section-gap">
            <div className="admin-card-title">Scheduler jobs</div>
            <div className="admin-table-wrap">
              <JobTable jobs={normalizedJobs} onRunNow={runNow} onPauseResume={pauseResume} mode="operator" />
            </div>
          </div>
        </>
      )}

      {tab === 'diagnostics' && (
        <div className="admin-card">
          <div className="admin-card-title">Diagnostic results</div>
          <div className="admin-card-body">
            {!diagResult && !intResult ? (
              <p className="admin-text-muted">Run a smoke test or integrity check from the Health tab.</p>
            ) : (
              <>
                {diagResult && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8, fontSize: 12, color: diagResult.ok ? 'var(--green)' : 'var(--red)' }}>
                      {diagResult.ok ? '✓ All checks passed' : '✗ Some checks failed'} ({diagResult.duration_ms}ms)
                    </div>
                    {diagResult.checks?.map((c, i) => (
                      <div key={i} style={{ fontSize: 12, display: 'flex', gap: 8, padding: '4px 0' }}>
                        <span style={{ color: c.passed ? 'var(--green)' : 'var(--red)' }}>{c.passed ? '✓' : '✗'}</span>
                        <span>{c.name}</span>
                        <span className="admin-text-dim">{c.detail}</span>
                      </div>
                    ))}
                  </div>
                )}
                {intResult && (
                  <div style={{ fontSize: 12 }}>
                    <span style={{ color: intResult.integrity_ok ? 'var(--green)' : 'var(--red)' }}>
                      {intResult.integrity_ok ? '✓ Integrity OK' : '✗ Integrity FAILED'}
                    </span>
                    {' — '}
                    <span style={{ color: intResult.foreign_keys_ok ? 'var(--green)' : 'var(--red)' }}>
                      {intResult.foreign_keys_ok ? '✓ FK OK' : `✗ ${intResult.foreign_key_violations} FK violations`}
                    </span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function OverviewPage({ system, toast, mode = 'analyst', jobAcks = [], onMarkJobErrorsRead }) {
  if (!system) return <div className="admin-loading"><span className="admin-spinner" /> Loading system status…</div>
  const shared = { system, toast, jobAcks, onMarkJobErrorsRead }
  return mode === 'analyst'
    ? <AnalystOverview {...shared} />
    : <OperatorOverview {...shared} />
}
