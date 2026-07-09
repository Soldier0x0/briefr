import { jobLabel } from '../catalog.js'
import { fmtIso } from '../formatters.js'
import { filterUnacknowledgedErrors } from '../adminJobAck.js'

export function jobErrorsFromSystem(system) {
  const fromRecent = system?.recent_errors || []
  if (fromRecent.length > 0) return fromRecent
  return (system?.scheduler_jobs || [])
    .filter(j => j.last_run_had_error)
    .map(j => ({
      job_id: j.id,
      error: (j.last_error_message || '').slice(0, 200),
      last_run_utc: j.last_run_utc,
    }))
}

export default function JobErrorsPanel({
  system,
  jobAcks,
  onMarkAllRead,
  onRetry,
  mode = 'operator',
  running = {},
}) {
  const allErrors = jobErrorsFromSystem(system)
  const visible = filterUnacknowledgedErrors(allErrors, jobAcks)

  if (allErrors.length === 0) return null

  return (
    <div className="admin-card">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
        <div className="admin-card-title" style={{ color: 'var(--red)', marginBottom: 0 }}>
          {mode === 'analyst' ? 'Scheduler problems' : 'Recent errors'}
          {visible.length > 0 && (
            <span className="nav-badge nav-badge-red" style={{ marginLeft: '0.5rem', verticalAlign: 'middle' }}>
              {visible.length}
            </span>
          )}
        </div>
        {visible.length > 0 && onMarkAllRead && (
          <button
            type="button"
            className="admin-btn admin-btn-ghost"
            style={{ fontSize: '0.75rem', marginLeft: 'auto' }}
            onClick={() => onMarkAllRead(allErrors)}
          >
            Mark all as read
          </button>
        )}
      </div>
      {visible.length === 0 ? (
        <div className="admin-empty" style={{ color: 'var(--text3)' }}>
          All current errors acknowledged — badge cleared until a job fails again.
        </div>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>{mode === 'analyst' ? 'NAME' : 'JOB ID'}</th>
              <th>ERROR</th>
              <th>LAST RUN</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visible.map(e => (
              <tr key={`${e.job_id}-${e.last_run_utc}`}>
                <td style={{ fontSize: '0.8rem' }}>
                  {mode === 'analyst' ? jobLabel(e.job_id, 'analyst') : jobLabel(e.job_id, 'operator')}
                </td>
                <td style={{ fontSize: '0.75rem', maxWidth: 360, wordBreak: 'break-word' }}>
                  {e.error || '—'}
                </td>
                <td style={{ fontSize: '0.75rem' }}>{fmtIso(e.last_run_utc)}</td>
                <td>
                  {onRetry && (
                    <button
                      type="button"
                      className="admin-btn admin-btn-ghost"
                      style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem' }}
                      disabled={!!running[e.job_id]}
                      onClick={() => onRetry(e.job_id)}
                    >
                      {running[e.job_id] ? 'Starting…' : 'Retry'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
