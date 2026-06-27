import {
  Activity, Archive, HardDrive, Database, Bookmark, KeyRound, Clock, Webhook,
  ShieldAlert, HeartPulse, ScrollText, ClipboardList, Settings2, LogIn, Users,
  Gauge, BellRing, Lock, ArrowRightLeft, LayoutDashboard,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { NAV, ANALYST_NAV } from './constants.js'

const ICONS = {
  Activity, Archive, HardDrive, Database, Bookmark, KeyRound, Clock, Webhook,
  ShieldAlert, HeartPulse, ScrollText, ClipboardList, Settings2, LogIn, Users,
  Gauge, BellRing,
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
      <div className="nav-scroll-area">
        {navConfig.map(section => (
          <div key={section.section}>
            <div className="nav-section-label">{section.section}</div>
            {section.items.map(item => {
              const badge = getBadge(item)
              const Icon = ICONS[item.icon]
              if (item.locked) {
                return (
                  <div
                    key={item.id}
                    className="nav-item nav-item-locked"
                    onClick={() => setPage(item.id)}
                    title={item.tooltip}
                  >
                    {Icon && <Icon className="nav-icon" size={15} strokeWidth={1.75} />}
                    <span>{item.label}</span>
                    <Lock className="nav-lock-icon" size={11} strokeWidth={2} />
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
                  {Icon && <Icon className="nav-icon" size={15} strokeWidth={1.75} />}
                  <span>{item.label}</span>
                  {badge > 0 && <span className={`nav-badge ${item.badgeKey === 'failed_auth_last_24h' ? 'nav-badge-amber' : 'nav-badge-red'}`}>{badge}</span>}
                </div>
              )
            })}
          </div>
        ))}
      </div>
      <div className="nav-sticky-footer">
        {mode === 'analyst' && setMode && (
          <button className="nav-footer-link" onClick={() => setMode('operator')}>
            <ArrowRightLeft size={13} strokeWidth={1.75} />
            <span>Backups, config, logs → switch to Operator view</span>
          </button>
        )}
        <Link to="/" className="nav-footer-link">
          <LayoutDashboard size={13} strokeWidth={1.75} />
          <span>Back to BRIEFR</span>
        </Link>
      </div>
    </nav>
  )
}
