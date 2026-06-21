import { useState, useEffect } from 'react'
import { adminApi } from '../../api.js'
import ConfirmModal from './shared/ConfirmModal.jsx'
import DangerZone from './shared/DangerZone.jsx'
import JobTable from './shared/JobTable.jsx'
import { MANUAL_PIPELINES } from './constants.js'

const STATUS_FILTERS = ['ACTIVE', 'PAUSED', 'LOCKED', 'DISABLED']
const PAGE_SIZE = 10

export default function SchedulerPage({ toast, system }) {
  const [jobs, setJobs] = useState(null)
  const [running, setRunning] = useState({})
  const [pauseAllConfirm, setPauseAllConfirm] = useState(false)
  const [resumeAllConfirm, setResumeAllConfirm] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(0)

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
    try {
      const res = await adminApi.post('/scheduler/pause-all', { confirm_text: 'pause' })
      const data = await res.json()
      toast(data.ok ? `Paused ${data.paused?.length ?? 0} job(s)` : 'Failed', data.ok)
      loadJobs()
    } catch (e) { toast(String(e.message), false) }
  }

  async function resumeAll() {
    setResumeAllConfirm(false)
    try {
      const res = await adminApi.post('/scheduler/resume-all', { confirm_text: 'resume' })
      const data = await res.json()
      toast(data.ok ? `Resumed ${data.resumed?.length ?? 0} job(s)` : 'Failed', data.ok)
      loadJobs()
    } catch (e) { toast(String(e.message), false) }
  }

  const activeLocks = system?.active_locks || []
  const filteredJobs = jobs ? (statusFilter ? jobs.filter(j => j.status === statusFilter) : jobs) : null

  useEffect(() => {
    if (filteredJobs && page > 0 && page * PAGE_SIZE >= filteredJobs.length) {
      setPage(Math.max(0, Math.ceil(filteredJobs.length / PAGE_SIZE) - 1))
    }
  }, [filteredJobs, page])

  const pagedJobs = filteredJobs ? filteredJobs.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE) : null

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

      <DangerZone title="Global controls">
        <div className="admin-action-bar">
          <button className="admin-btn admin-btn-danger" onClick={() => setPauseAllConfirm(true)}>Pause all jobs</button>
          <button className="admin-btn admin-btn-primary" onClick={() => setResumeAllConfirm(true)}>Resume all jobs</button>
        </div>
      </DangerZone>

      <div className="admin-card">
        <div className="admin-card-title">All jobs</div>
        <div className="admin-filter-chips" style={{ marginBottom: '0.75rem' }}>
          <button className={`filter-chip ${statusFilter === '' ? 'active' : ''}`} onClick={() => { setStatusFilter(''); setPage(0) }}>All</button>
          {STATUS_FILTERS.map(s => (
            <button key={s} className={`filter-chip ${statusFilter === s ? 'active' : ''}`} onClick={() => { setStatusFilter(s); setPage(0) }}>
              {s}
            </button>
          ))}
        </div>
        <JobTable jobs={pagedJobs} onRunNow={runNow} onPauseResume={pauseResume} />
        {filteredJobs && filteredJobs.length > PAGE_SIZE && (
          <div className="admin-pagination">
            <button className="admin-btn admin-btn-ghost" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
            <span style={{ color: 'var(--text3)', fontSize: '0.8125rem' }}>
              {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filteredJobs.length)} of {filteredJobs.length}
            </span>
            <button className="admin-btn admin-btn-ghost" disabled={(page + 1) * PAGE_SIZE >= filteredJobs.length} onClick={() => setPage(p => p + 1)}>Next →</button>
          </div>
        )}
      </div>
    </div>
  )
}
