import { NAV, ANALYST_NAV } from './constants.js'

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
    </nav>
  )
}
