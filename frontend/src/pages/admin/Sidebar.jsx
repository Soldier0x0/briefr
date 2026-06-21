import { NAV, ANALYST_NAV } from './constants.js'

const STATUS_LEGEND = [
  { swatch: 'badge-ok', label: 'ACTIVE', meaning: 'Job is scheduled and will run normally' },
  { swatch: 'badge-warn', label: 'PAUSED', meaning: "Won't run until resumed — safe to leave while debugging" },
  { swatch: 'badge-info', label: 'LOCKED', meaning: "Currently running right now — don't restart the backend" },
  { swatch: 'badge-muted', label: 'DISABLED', meaning: 'Turned off via an env var, not a runtime state' },
  { swatch: 'pill-green', label: 'Discord/Telegram green', meaning: 'Configured and last delivery succeeded' },
  { swatch: 'pill-amber', label: 'Discord/Telegram amber', meaning: 'Configured but the circuit is open (failing)' },
  { swatch: 'pill-gray', label: 'Discord/Telegram gray', meaning: 'Not configured' },
  { swatch: 'dot-ok', label: 'DB ok', meaning: 'Last integrity check passed' },
  { swatch: 'dot-error', label: 'DB degraded', meaning: 'Last integrity check found a problem' },
]

const ANALYST_STATUS_LEGEND = [
  { swatch: 'badge-ok', label: 'Current', meaning: 'Data is fresh' },
  { swatch: 'badge-warn', label: 'Delayed', meaning: 'Older than expected' },
  { swatch: 'badge-info', label: 'Updating', meaning: 'Sync in progress' },
]

function StatusLegend({ mode }) {
  const legend = mode === 'analyst' ? ANALYST_STATUS_LEGEND : STATUS_LEGEND
  return (
    <details className="status-legend">
      <summary>Status legend</summary>
      <ul>
        {legend.map(s => (
          <li key={s.label}>
            <span className={`status-legend-swatch ${s.swatch}`} />
            <span className="status-legend-text">
              <strong>{s.label}</strong> — {s.meaning}
            </span>
          </li>
        ))}
      </ul>
    </details>
  )
}

export default function Sidebar({ activePage, setPage, system, ingestErrorCount, mode, setMode }) {
  const openCircuits = system?.open_circuit_count || 0
  const failedAuth = system?.failed_auth_last_24h || 0
  const jobErrors = system?.jobs_with_errors_count || 0
  const navConfig = mode === 'analyst' ? ANALYST_NAV : NAV

  function getBadge(item) {
    if (item.badgeKey === 'open_circuit_count') return openCircuits
    if (item.badgeKey === 'failed_auth_last_24h') return failedAuth
    if (item.badgeKey === 'jobs_with_errors_count') return jobErrors
    if (item.badgeKey === 'ingest_error_count') return ingestErrorCount
    return 0
  }

  return (
    <nav className="admin-sidebar">
      {navConfig.map(section => (
        <div key={section.section}>
          <div className="nav-section-label">{section.section}</div>
          {section.items.map(item => {
            const badge = getBadge(item)
            if (item.locked) {
              return (
                <div
                  key={item.id}
                  className="nav-item nav-item-locked"
                  onClick={() => setPage(item.id)}
                  title={item.tooltip}
                >
                  <span className="nav-lock-icon">🔒</span>
                  <span>{item.label}</span>
                  {item.tooltip && <span className="nav-item-tooltip">{item.tooltip}</span>}
                </div>
              )
            }
            return (
              <div
                key={item.id}
                className={`nav-item ${activePage === item.id ? 'active' : ''}`}
                onClick={() => setPage(item.id)}
              >
                {item.label}
                {badge > 0 && <span className={`nav-badge ${item.badgeKey === 'failed_auth_last_24h' ? 'nav-badge-amber' : 'nav-badge-red'}`}>{badge}</span>}
              </div>
            )
          })}
        </div>
      ))}
      {mode === 'analyst' && setMode && (
        <button className="nav-footer-link" onClick={() => setMode('operator')}>
          Backups, config, logs → switch to Operator view
        </button>
      )}
      <StatusLegend mode={mode} />
    </nav>
  )
}
