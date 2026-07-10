import { useState, useEffect } from 'react'
import { adminApi, getAdminRequestId } from '../../api.js'
import ConfirmModal from './shared/ConfirmModal.jsx'
import DangerZone from './shared/DangerZone.jsx'
import HelpTip from './shared/HelpTip.jsx'
import JobTable from './shared/JobTable.jsx'
import { useOperations } from './shared/OperationTracker.jsx'
import { MANUAL_PIPELINES } from './constants.js'
import { jobLabel } from './catalog.js'
import { canRunNow, pauseResumeAction } from './jobActions.js'
import {
  schedulerJobManualRun,
  schedulerJobPaused,
  schedulerJobResumed,
  schedulerJobRetry,
} from './toastCopy.js'

const STATUS_FILTERS = ['ACTIVE', 'PAUSED', 'LOCKED', 'DISABLED']
const PAGE_SIZE = 10

export default function SchedulerPage({ toast, system }) {
  const { runAction } = useOperations()
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

  async function runNow(jobId, { retry = false } = {}) {
    setRunning(r => ({ ...r, [jobId]: true }))
    try {
      await runAction({
        id: `job-${jobId}`,
        label: `Running ${jobLabel(jobId, 'operator')}`,
        kind: 'job',
        meta: { jobId },
        successMessage: retry
          ? schedulerJobRetry(jobId, 'operator')
          : schedulerJobManualRun(jobId, 'operator'),
        execute: async () => {
          const res = await adminApi.post('/scheduler/run', { job_id: jobId })
          const requestId = getAdminRequestId(res)
          const data = await res.json().catch(() => ({}))
          if (res.status === 409) {
            const err = new Error('Already running')
            err.requestId = requestId
            throw err
          }
          if (!res.ok || !data.ok) {
            const err = new Error(data.detail || `HTTP ${res.status}`)
            err.requestId = requestId
            throw err
          }
          return { requestId, data }
        },
      })
      setTimeout(loadJobs, 1000)
    } catch {
      // runAction already surfaced toast + log links
    } finally {
      setTimeout(() => setRunning(r => ({ ...r, [jobId]: false })), 2000)
    }
  }

  async function pauseResume(job) {
    const action = pauseResumeAction(job.status)
    if (!action) return
    try {
      const res = await adminApi.post(`/scheduler/${action}`, { job_id: job.id })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `HTTP ${res.status}`)
      }
      toast(action === 'pause' ? schedulerJobPaused(job.id, 'operator') : schedulerJobResumed(job.id, 'operator'), true)
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
        <div className="admin-card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          Manual triggers
          <HelpTip text="Run an individual data sync right now without waiting for the schedule. A job shows 'Running…' while active and cannot be triggered again until it finishes (LOCKED status)." />
        </div>
        <div className="admin-action-bar" style={{ flexWrap: 'wrap' }}>
          {MANUAL_PIPELINES.map(p => {
            const job = (jobs || []).find(j => j.id === p.id)
            const locked = job?.status === 'LOCKED' || running[p.id]
            const disabled = job?.status === 'DISABLED'
            return (
              <button
                key={p.id}
                className="admin-btn admin-btn-ghost"
                style={{ fontSize: '0.8125rem' }}
                onClick={() => runNow(p.id)}
                disabled={jobs === null || locked || disabled || !canRunNow(job?.status ?? 'ACTIVE')}
              >
                {locked ? <><span className="admin-spinner" /> Running…</> : p.label}
              </button>
            )
          })}
        </div>
        {activeLocks.length > 0 && (
          <div style={{ fontSize: '0.75rem', color: 'var(--amber)', marginTop: '0.5rem' }}>
            {activeLocks.map(l => jobLabel(l.job_id, 'operator')).join(', ')} currently running
          </div>
        )}
      </div>

      <div className="admin-card">
        <div className="admin-card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          All jobs
          <HelpTip text="ACTIVE = running on schedule. PAUSED = won't run until you resume it. LOCKED = currently executing (can't be triggered again until done). DISABLED = registered but turned off in configuration — enable the matching setting under API keys & config." />
        </div>
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

      <DangerZone title="Global controls" subdued>
        <div className="admin-action-bar">
          <button className="admin-btn admin-btn-danger" onClick={() => setPauseAllConfirm(true)}>Pause all jobs</button>
          <button className="admin-btn admin-btn-primary" onClick={() => setResumeAllConfirm(true)}>Resume all jobs</button>
        </div>
      </DangerZone>
    </div>
  )
}
