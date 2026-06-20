import { Fragment, useState } from 'react'
import { fmtIso, fmtDur } from '../formatters.js'

const STATUS_TITLES = {
  ACTIVE: 'Job is scheduled and will run normally',
  PAUSED: "Won't run until resumed — safe to leave while debugging",
  LOCKED: "Currently running right now — don't restart the backend",
  DISABLED: 'Turned off via an env var, not a runtime state',
}

export function JobStatusBadge({ status }) {
  const map = {
    ACTIVE: 'badge-ok',
    PAUSED: 'badge-warn',
    LOCKED: 'badge-info',
    DISABLED: 'badge-muted',
  }
  return <span className={`badge ${map[status] || 'badge-muted'}`} title={STATUS_TITLES[status]}>{status}</span>
}

// Shared scheduler job table (used by Overview and Scheduler pages).
export default function JobTable({ jobs, onRunNow, onPauseResume, expandErrors = true }) {
  const [expanded, setExpanded] = useState({})
  if (!jobs) return <div className="admin-empty">Loading…</div>
  if (jobs.length === 0) return <div className="admin-empty">No jobs registered</div>

  return (
    <table className="admin-table">
      <thead>
        <tr>
          <th>JOB ID</th><th>NAME</th><th>STATUS</th><th>LAST RUN</th>
          <th>DURATION</th><th>RECORDS</th><th>ERROR</th><th>NEXT RUN</th><th>ACTIONS</th>
        </tr>
      </thead>
      <tbody>
        {jobs.map(job => (
          <Fragment key={job.id}>
            <tr key={job.id}>
              <td className="mono" style={{ fontSize: '0.7rem' }}>{job.id}</td>
              <td style={{ fontSize: '0.8rem' }}>{job.name}</td>
              <td><JobStatusBadge status={job.status} /></td>
              <td style={{ fontSize: '0.75rem' }}>{fmtIso(job.last_run_utc)}</td>
              <td>{fmtDur(job.last_run_duration_seconds)}</td>
              <td>{job.last_run_records_upserted ?? '—'}</td>
              <td>
                {job.last_run_had_error === true ? (
                  <button
                    className="badge badge-error"
                    style={{ cursor: expandErrors ? 'pointer' : 'default', background: 'none', border: 'none' }}
                    onClick={() => expandErrors && setExpanded(e => ({ ...e, [job.id]: !e[job.id] }))}
                  >
                    ERROR {expandErrors ? (expanded[job.id] ? '▲' : '▼') : ''}
                  </button>
                ) : job.last_run_had_error === false ? '' : '—'}
              </td>
              <td style={{ fontSize: '0.75rem' }} title={job.status === 'PAUSED' ? 'Job is paused — will not run until resumed' : undefined}>
                {job.status === 'PAUSED' ? '(paused)' : fmtIso(job.next_run_time)}
              </td>
              <td>
                <div style={{ display: 'flex', gap: '0.3rem' }}>
                  {onRunNow && (
                    <button
                      className="admin-btn admin-btn-ghost"
                      style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem' }}
                      onClick={() => onRunNow(job.id)}
                      disabled={job.status === 'LOCKED'}
                    >Run</button>
                  )}
                  {onPauseResume && (
                    <button
                      className={`admin-btn ${job.status === 'PAUSED' ? 'admin-btn-primary' : 'admin-btn-warn'}`}
                      style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem' }}
                      onClick={() => onPauseResume(job)}
                    >
                      {job.status === 'PAUSED' ? 'Resume' : 'Pause'}
                    </button>
                  )}
                </div>
              </td>
            </tr>
            {expandErrors && expanded[job.id] && job.last_error_message && (
              <tr key={`${job.id}-err`}>
                <td colSpan={9} style={{ background: 'var(--bg3)', padding: '0.5rem 0.75rem' }}>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--red)', wordBreak: 'break-all' }}>
                    {job.last_error_message}
                  </div>
                  {onRunNow && (
                    <button
                      className="admin-btn admin-btn-ghost"
                      style={{ marginTop: '0.4rem', fontSize: '0.75rem' }}
                      onClick={() => onRunNow(job.id)}
                    >
                      Retry now
                    </button>
                  )}
                </td>
              </tr>
            )}
          </Fragment>
        ))}
      </tbody>
    </table>
  )
}
