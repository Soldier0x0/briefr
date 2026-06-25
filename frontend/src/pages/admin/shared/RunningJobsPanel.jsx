import { jobLabel } from '../catalog.js'
import { JobStatusBadge } from './JobTable.jsx'

/** Consistent "jobs currently running" list — same labels as JobTable. */
export default function RunningJobsPanel({
  jobs,
  mode = 'operator',
  showTechnicalIds = false,
  emptyText = 'No jobs running',
}) {
  if (!jobs?.length) {
    return <div className="admin-empty">{emptyText}</div>
  }

  return (
    <table className="admin-table">
      <thead>
        <tr>
          {showTechnicalIds && <th>JOB ID</th>}
          <th>NAME</th>
          <th>STATUS</th>
        </tr>
      </thead>
      <tbody>
        {jobs.map((job) => (
          <tr key={job.id}>
            {showTechnicalIds && (
              <td className="mono" style={{ fontSize: '0.75rem' }}>{job.id}</td>
            )}
            <td style={{ fontSize: '0.8rem' }}>{jobLabel(job.id, mode) || job.name}</td>
            <td><JobStatusBadge status="LOCKED" mode={mode} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
