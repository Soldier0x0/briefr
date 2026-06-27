import { Fragment, useState } from 'react'
import { fmtIso, fmtDur } from '../formatters.js'
import { jobLabel, statusLabel, statusHint } from '../catalog.js'
import { getDisplayPrefs, setDisplayPrefs } from '../../../utils/displayPrefs.js'

const STATUS_CLASS = {
  ACTIVE: 'active',
  PAUSED: 'paused',
  LOCKED: 'locked',
  DISABLED: 'disabled',
}

export function JobStatusBadge({ status, mode = 'operator' }) {
  const tone = STATUS_CLASS[status] || 'disabled'
  return (
    <span title={statusHint(status)}>
      <span className={`admin-job-status admin-job-status--${tone}`}>
        {statusLabel(status, mode)}
      </span>
      {mode === 'analyst' && <span className="status-hint-text">{statusHint(status)}</span>}
    </span>
  )
}

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
          <tr>
            <th className="admin-table-sticky">Name</th>
            <th>Status</th>
            <th>Cadence</th>
            <th>Last run</th>
            <th>Next run</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map(job => (
            <tr key={job.id}>
              <td className="admin-table-sticky">{jobLabel(job.id, 'analyst')}</td>
              <td><JobStatusBadge status={job.status} mode="analyst" /></td>
              <td className="admin-text-dim">{job.schedule_cadence || '—'}</td>
              <td>{fmtIso(job.last_run_utc)}</td>
              <td>{job.status === 'PAUSED' ? '(paused)' : fmtIso(job.next_run_time)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  const colCount = (showIds ? 10 : 9)

  return (
    <div>
      <label className="admin-checkbox-label" style={{ fontSize: 12, marginBottom: 8, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <input type="checkbox" checked={showIds} onChange={e => toggleShowIds(e.target.checked)} />
        Show technical IDs
      </label>
      <table className="admin-table">
        <thead>
          <tr>
            {showIds && <th>Job ID</th>}
            <th className="admin-table-sticky">Name</th>
            <th>Status</th>
            <th>Cadence</th>
            <th>Last run</th>
            <th>Duration</th>
            <th>Records</th>
            <th>Error</th>
            <th>Next run</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map(job => (
            <Fragment key={job.id}>
              <tr>
                {showIds && <td className="mono admin-text-dim" style={{ fontSize: 11 }}>{job.id}</td>}
                <td className="admin-table-sticky">{jobLabel(job.id, 'operator') || job.name}</td>
                <td><JobStatusBadge status={job.status} mode="operator" /></td>
                <td className="admin-text-dim">{job.schedule_cadence || '—'}</td>
                <td>{fmtIso(job.last_run_utc)}</td>
                <td>{fmtDur(job.last_run_duration_seconds)}</td>
                <td>{job.last_run_records_upserted ?? '—'}</td>
                <td>
                  {job.last_run_had_error === true ? (
                    <button
                      type="button"
                      className="badge badge-error"
                      style={{ cursor: expandErrors ? 'pointer' : 'default', background: 'none', border: 'none' }}
                      onClick={() => expandErrors && setExpanded(e => ({ ...e, [job.id]: !e[job.id] }))}
                    >
                      ERROR {expandErrors ? (expanded[job.id] ? '▲' : '▼') : ''}
                    </button>
                  ) : job.last_run_had_error === false ? '' : '—'}
                </td>
                <td title={job.status === 'PAUSED' ? 'Job is paused — will not run until resumed' : undefined}>
                  {job.status === 'PAUSED' ? '(paused)' : fmtIso(job.next_run_time)}
                </td>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {onRunNow && (
                      <button
                        type="button"
                        className="admin-btn admin-btn-ghost admin-btn--sm"
                        onClick={() => onRunNow(job.id)}
                        disabled={job.status === 'LOCKED'}
                      >Run</button>
                    )}
                    {onPauseResume && (
                      <button
                        type="button"
                        className={`admin-btn admin-btn--sm ${job.status === 'PAUSED' ? 'admin-btn-primary' : 'admin-btn-warn'}`}
                        onClick={() => onPauseResume(job)}
                      >
                        {job.status === 'PAUSED' ? 'Resume' : 'Pause'}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
              {expandErrors && expanded[job.id] && (
                <tr>
                  <td colSpan={colCount} style={{ background: 'var(--bg3)', padding: '10px 12px' }}>
                    <div className="mono" style={{ fontSize: 12, color: 'var(--red)', wordBreak: 'break-all' }}>
                      {job.last_error_message || 'An unknown error occurred during the last run.'}
                    </div>
                    {onRunNow && (
                      <button
                        type="button"
                        className="admin-btn admin-btn-ghost admin-btn--sm"
                        style={{ marginTop: 8 }}
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
