import { HelpCircle } from 'lucide-react'
import { CIRCUIT_UI } from '../circuitLabels.js'
import { statusLabel } from '../catalog.js'

const LEGEND = [
  { tag: 'ACTIVE', className: 'active', desc: 'Scheduled and running on its interval.' },
  { tag: 'PAUSED', className: 'paused', desc: "Won't run until you resume it (operator pause)." },
  {
    tag: statusLabel('LOCKED'),
    className: 'locked',
    desc: "Currently executing — can't be triggered again until done.",
  },
  { tag: 'DISABLED', className: 'disabled', desc: 'Turned off in configuration (API keys & config).' },
  { tag: CIRCUIT_UI.legendTag, className: 'circuit', desc: CIRCUIT_UI.legendDesc },
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
