import { HelpCircle } from 'lucide-react'

const LEGEND = [
  { tag: 'ACTIVE', className: 'active', desc: 'Job is scheduled and running on its interval.' },
  { tag: 'PAUSED', className: 'paused', desc: 'Temporarily stopped; resume when ready.' },
  { tag: 'LOCKED', className: 'locked', desc: 'Blocked by dependency or global pause.' },
  { tag: 'DISABLED', className: 'disabled', desc: 'Turned off in configuration.' },
  { tag: 'CIRCUIT', className: 'circuit', desc: 'Upstream source tripped the circuit breaker.' },
]

export default function StatusLegend({ compact = false }) {
  return (
    <div className="admin-status-legend" aria-label="Job status legend">
      <div className="admin-status-legend-title">
        <HelpCircle size={12} aria-hidden />
        {compact ? 'Statuses' : 'Status legend'}
      </div>
      {LEGEND.map((row) => (
        <div key={row.tag} className="admin-status-legend-row">
          <span className={`admin-status-legend-tag admin-status-legend-tag--${row.className}`}>
            {row.tag}
          </span>
          <span>{row.desc}</span>
        </div>
      ))}
    </div>
  )
}
