import { useState, useEffect } from 'react'
import { adminApi } from '../../api.js'
import ConfirmModal from './shared/ConfirmModal.jsx'
import JobTable from './shared/JobTable.jsx'
import { MANUAL_PIPELINES } from './constants.js'

export default function SchedulerPage({ toast, system }) {
  const [jobs, setJobs] = useState(null)
  const [running, setRunning] = useState({})
  const [pauseAllConfirm, setPauseAllConfirm] = useState(false)
  const [resumeAllConfirm, setResumeAllConfirm] = useState(false)

  async function loadJobs() {
    try {
      const res = await adminApi.get('/scheduler')
      setJobs(await res.json())
    } catch { }
  }

  useEffect(() => { loadJobs() }, [])

  async function runNow(jobId) {
    setRunning(r => ({ ...r, [jobId]: true }))
    try {
      const res = await adminApi.post('/scheduler/run', { job_id: jobId })
      const data = await res.json()
      if (res.status === 409) { toast('Already running', false); return }
      toast(data.ok ? `Started: ${jobId}` : data.detail || 'Failed', data.ok)
      setTimeout(loadJobs, 1000)
    } catch (e) { toast(String(e.message), false) }
    setTimeout(() => setRunning(r => ({ ...r, [jobId]: false })), 2000)
  }

  async function pauseResume(job) {
    const action = job.status === 'PAUSED' ? 'resume' : 'pause'
    try {
      await adminApi.post(`/scheduler/${action}`, { job_id: job.id })
      toast(`Job ${action}d`, true)
      loadJobs()
    } catch (e) { toast(String(e.message), false) }
  }

  async function pauseAll() {
    setPauseAllConfirm(false)
    const jobList = jobs || []
    for (const job of jobList) {
      if (job.status === 'ACTIVE') {
        await adminApi.post('/scheduler/pause', { job_id: job.id })
      }
    }
    toast('All active jobs paused', true)
    loadJobs()
  }

  async function resumeAll() {
    setResumeAllConfirm(false)
    const jobList = jobs || []
    for (const job of jobList) {
      if (job.status === 'PAUSED') {
        await adminApi.post('/scheduler/resume', { job_id: job.id })
      }
    }
    toast('All paused jobs resumed', true)
    loadJobs()
  }

  const activeLocks = system?.active_locks || []

  return (
    <div>
      {pauseAllConfirm && (
        <ConfirmModal
          title="Pause all jobs?"
          message="This will pause all active scheduler jobs. No scheduled syncs will run until resumed."
          confirmWord="pause"
          onConfirm={pauseAll}
          onCancel={() => setPauseAllConfirm(false)}
        />
      )}
      {resumeAllConfirm && (
        <ConfirmModal
          title="Resume all jobs?"
          message="This will resume every paused scheduler job."
          confirmWord="resume"
          onConfirm={resumeAll}
          onCancel={() => setResumeAllConfirm(false)}
        />
      )}

      <h1 className="admin-page-title">Scheduler</h1>

      <div className="admin-card">
        <div className="admin-card-title">Manual triggers</div>
        <div className="admin-action-bar" style={{ flexWrap: 'wrap' }}>
          {MANUAL_PIPELINES.map(p => {
            const job = (jobs || []).find(j => j.id === p.id)
            const locked = job?.status === 'LOCKED' || running[p.id]
            return (
              <button
                key={p.id}
                className="admin-btn admin-btn-ghost"
                style={{ fontSize: '0.8125rem' }}
                onClick={() => runNow(p.id)}
                disabled={locked}
              >
                {locked ? <><span className="admin-spinner" /> Running…</> : p.label}
              </button>
            )
          })}
        </div>
        {activeLocks.length > 0 && (
          <div style={{ fontSize: '0.75rem', color: 'var(--amber)', marginTop: '0.5rem' }}>
            {activeLocks.map(l => l.job_id).join(', ')} currently running
          </div>
        )}
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Global controls</div>
        <div className="admin-action-bar">
          <button className="admin-btn admin-btn-danger" onClick={() => setPauseAllConfirm(true)}>Pause all jobs</button>
          <button className="admin-btn admin-btn-primary" onClick={() => setResumeAllConfirm(true)}>Resume all jobs</button>
        </div>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">All jobs</div>
        <JobTable jobs={jobs} onRunNow={runNow} onPauseResume={pauseResume} />
      </div>
    </div>
  )
}
