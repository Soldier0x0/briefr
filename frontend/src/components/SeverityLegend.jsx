import { HelpCircle } from 'lucide-react'
import { SEVERITY_LEVELS } from '../utils/severitySemantics.js'
import './SeverityLegend.css'

/**
 * Discoverable CVSS severity scale (E4-4). Pair with portaled tooltips on badges.
 */
export default function SeverityLegend({ compact = false, className = '' }) {
  return (
    <div
      className={`severity-legend${className ? ` ${className}` : ''}`}
      aria-label="CVSS severity legend"
    >
      <div className="severity-legend-title">
        <HelpCircle size={12} aria-hidden />
        {compact ? 'Severity' : 'Severity legend'}
      </div>
      {SEVERITY_LEVELS.map((row) => (
        <div key={row.id} className="severity-legend-row">
          <span className="severity-legend-marker">
            <span className={`sev-dot sev-dot-${row.className}`} aria-hidden="true" />
            <span className="severity-legend-label mono">{row.label}</span>
          </span>
          <span className="severity-legend-desc">{row.desc}</span>
        </div>
      ))}
    </div>
  )
}
