import { Fragment, useState } from 'react'
import { fmtIso, fmtDur } from '../formatters.js'
import { jobLabel, statusLabel, statusHint } from '../catalog.js'
import { getDisplayPrefs, setDisplayPrefs } from '../../../utils/displayPrefs.js'

export function JobStatusBadge({ status, mode = 'operator' }) {
  const map = {
    ACTIVE: 'badge-ok',
    PAUSED: 'badge-warn',
    LOCKED: 'badge-info',
    DISABLED: 'badge-muted',
  }
  return (
    <span>
      <span className={`badge ${map[status] || 'badge-muted'}`} title={statusHint(status)}>{statusLabel(status, mode)}</span>
      {mode === 'analyst' && <span className="status-hint-text">{statusHint(status)}</span>}
    </span>
  )
}

// Shared scheduler job table (used by Overview and Scheduler pages).
export default function JobTable({ jobs, onRunNow, onPauseResume, expandErrors = true, mode = 'operator' }) {
  const [expanded, setExpanded] = useState({})
  const [showIds, setShowIds] = useState(() => getDisplayPrefs().showTechnicalIds)

  function toggleShowIds(v) {
    setShowIds(v)
    setDisplayPrefs({ showTechnicalIds: v })
  }

  if (!jobs) return <div className="admin-empty">Loading…</div>
  if (jobs.length === 0) return <div className="admin-empty">No jobs registered</div>

  if (mode === 'analyst') {
    return (
      <table className="admin-table">
        <thead>
          <tr><th>NAME</th><th>STATUS</th><th>LAST RUN</th><th>NEXT RUN</th></tr>
        </thead>
        <tbody>
          {jobs.map(job => (
            <tr key={job.id}>
              <td style={{ fontSize: '0.8rem' }}>{jobLabel(job.id, 'analyst')}</td>
              <td><JobStatusBadge status={job.status} mode="analyst" /></td>
              <td style={{ fontSize: '0.75rem' }}>{fmtIso(job.last_run_utc)}</td>
              <td style={{ fontSize: '0.75rem' }}>
                {job.status === 'PAUSED' ? '(paused)' : fmtIso(job.next_run_time)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  return (
    <div>
      <label className="admin-checkbox-label" style={{ fontSize: '0.75rem', marginBottom: '0.4rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
        <input type="checkbox" checked={showIds} onChange={e => toggleShowIds(e.target.checked)} />
        Show technical IDs
      </label>
      <table className="admin-table">
        <thead>
          <tr>
            {showIds && <th>JOB ID</th>}<th>NAME</th><th>STATUS</th><th>LAST RUN</th>
            <th>DURATION</th><th>RECORDS</th><th>ERROR</th><th>NEXT RUN</th><th>ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map(job => (
            <Fragment key={job.id}>
              <tr key={job.id}>
                {showIds && <td className="mono" style={{ fontSize: '0.7rem' }}>{job.id}</td>}
                <td style={{ fontSize: '0.8rem' }}>{jobLabel(job.id, 'operator') || job.name}</td>
                <td><JobStatusBadge status={job.status} mode="operator" /></td>
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
                        style={{ fontSize: '0.8125rem', padding: '0.35rem 0.85rem' }}
                        onClick={() => onRunNow(job.id)}
                        disabled={job.status === 'LOCKED'}
                      >Run</button>
                    )}
                    {onPauseResume && (
                      <button
                        className={`admin-btn ${job.status === 'PAUSED' ? 'admin-btn-primary' : 'admin-btn-warn'}`}
                        style={{ fontSize: '0.8125rem', padding: '0.35rem 0.85rem' }}
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
                  <td colSpan={showIds ? 9 : 8} style={{ background: 'var(--bg3)', padding: '0.5rem 0.75rem' }}>
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
    </div>
  )
}
