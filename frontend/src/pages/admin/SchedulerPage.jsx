import { useState, useEffect } from 'react'
import { adminApi } from '../../api.js'
import ConfirmModal from './shared/ConfirmModal.jsx'
import DangerZone from './shared/DangerZone.jsx'
import JobTable from './shared/JobTable.jsx'
import RunningJobsPanel from './shared/RunningJobsPanel.jsx'
import OperatorSystemActions from './shared/OperatorSystemActions.jsx'
import ActionProgress from './shared/ActionProgress.jsx'
import { MANUAL_PIPELINES } from './constants.js'
import { statusLabel } from './catalog.js'
import {
  getRunningJobs,
  getSchedulerJobs,
  isJobRunning,
  jobById,
} from './jobStatus.js'

const STATUS_FILTERS = ['ACTIVE', 'PAUSED', 'LOCKED', 'DISABLED']

export default function SchedulerPage({
  toast,
  system,
  onRunIngest,
  onRestart,
  onDrainRestart,
  onRefreshSystem,
}) {
  const [jobsFallback, setJobsFallback] = useState(null)
  const [running, setRunning] = useState({})
  const [pauseAllConfirm, setPauseAllConfirm] = useState(false)
  const [resumeAllConfirm, setResumeAllConfirm] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')
  const [progress, setProgress] = useState(null)

  const schedulerJobs = getSchedulerJobs(system, jobsFallback)
  const runningJobs = getRunningJobs(system, jobsFallback)

  async function loadJobsFallback() {
    try {
      const res = await adminApi.get('/scheduler')
      setJobsFallback(await res.json())
    } catch { /* polled system is primary */ }
  }

  useEffect(() => { loadJobsFallback() }, [])

  function refreshSchedulerState() {
    onRefreshSystem?.()
    loadJobsFallback()
  }

  async function runNow(jobId) {
    setRunning(r => ({ ...r, [jobId]: true }))
    setProgress({ label: `Starting ${jobId}…`, stage: 'Sending run request to scheduler' })
    try {
      const res = await adminApi.post('/scheduler/run', { job_id: jobId })
      const data = await res.json()
      if (res.status === 409) {
        toast('Already running', false)
        setProgress(null)
        return
      }
      toast(data.ok ? `Started: ${jobId}` : data.detail || 'Failed', data.ok)
      setProgress({ label: data.ok ? 'Job accepted' : 'Job rejected', stage: data.detail || jobId })
      refreshSchedulerState()
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
      await adminApi.post(`/scheduler/${action}`, { job_id: job.id })
      toast(`Job ${action}d`, true)
      refreshSchedulerState()
    } catch (e) { toast(String(e.message), false) }
  }

  async function pauseAll() {
    setPauseAllConfirm(false)
    try {
      const res = await adminApi.post('/scheduler/pause-all', { confirm_text: 'pause' })
      const data = await res.json()
      toast(data.ok ? `Paused ${data.paused?.length ?? 0} job(s)` : 'Failed', data.ok)
      refreshSchedulerState()
    } catch (e) { toast(String(e.message), false) }
  }

  async function resumeAll() {
    setResumeAllConfirm(false)
    try {
      const res = await adminApi.post('/scheduler/resume-all', { confirm_text: 'resume' })
      const data = await res.json()
      toast(data.ok ? `Resumed ${data.resumed?.length ?? 0} job(s)` : 'Failed', data.ok)
      refreshSchedulerState()
    } catch (e) { toast(String(e.message), false) }
  }

  const filteredJobs = schedulerJobs
    ? (statusFilter ? schedulerJobs.filter(j => j.status === statusFilter) : schedulerJobs)
    : null

  return (
    <div>
      {pauseAllConfirm && (
        <ConfirmModal
          actionId="scheduler.pause_all"
          title="Pause all jobs?"
          onConfirm={pauseAll}
          onCancel={() => setPauseAllConfirm(false)}
        />
      )}
      {resumeAllConfirm && (
        <ConfirmModal
          actionId="scheduler.resume_all"
          title="Resume all jobs?"
          onConfirm={resumeAll}
          onCancel={() => setResumeAllConfirm(false)}
        />
      )}

      <h1 className="admin-page-title">Data refresh schedule</h1>
      <p className="admin-page-subtitle">Controls when each ingest job runs. Pausing a job stops it from running automatically until resumed — safe to pause individual jobs while debugging a feed issue.</p>

      <ActionProgress label={progress?.label} stage={progress?.stage} visible={!!progress} />

      <div className="admin-card">
        <div className="admin-card-title">Manual triggers</div>
        <div className="admin-action-bar" style={{ flexWrap: 'wrap' }}>
          {MANUAL_PIPELINES.map(p => {
            const job = jobById(schedulerJobs, p.id)
            const busy = isJobRunning(job) || running[p.id]
            return (
              <button
                key={p.id}
                className="admin-btn admin-btn-ghost"
                style={{ fontSize: '0.8125rem' }}
                onClick={() => runNow(p.id)}
                disabled={busy}
              >
                {busy ? (
                  <><span className="admin-spinner" /> {statusLabel('LOCKED', 'operator')}…</>
                ) : p.label}
              </button>
            )
          })}
        </div>
        {runningJobs.length > 0 && (
          <div style={{ marginTop: '0.75rem' }}>
            <RunningJobsPanel jobs={runningJobs} mode="operator" showTechnicalIds />
          </div>
        )}
      </div>

      <div className="admin-card">
        <div className="admin-card-title">All jobs</div>
        <div className="admin-filter-chips" style={{ marginBottom: '0.75rem' }}>
          <button className={`filter-chip ${statusFilter === '' ? 'active' : ''}`} onClick={() => setStatusFilter('')}>All</button>
          {STATUS_FILTERS.map(s => (
            <button key={s} className={`filter-chip ${statusFilter === s ? 'active' : ''}`} onClick={() => setStatusFilter(s)}>
              {statusLabel(s, 'operator')}
            </button>
          ))}
        </div>
        <JobTable jobs={filteredJobs} onRunNow={runNow} onPauseResume={pauseResume} />
      </div>

      <DangerZone title="Global controls">
        <div className="admin-action-bar">
          <button className="admin-btn admin-btn-danger" onClick={() => setPauseAllConfirm(true)}>Pause all jobs</button>
          <button className="admin-btn admin-btn-primary" onClick={() => setResumeAllConfirm(true)}>Resume all jobs</button>
        </div>
      </DangerZone>

      <OperatorSystemActions
        onRunIngest={onRunIngest}
        onRestart={onRestart}
        onDrainRestart={onDrainRestart}
        refreshInProgress={system?.refresh_in_progress || false}
      />
    </div>
  )
}
