import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Eye, Wrench, RefreshCw, Clock, Menu, X, Shield } from 'lucide-react'
import HelpTip from './shared/HelpTip.jsx'
import ApiQueueIndicator from '../../components/ApiQueueIndicator.jsx'
import { fmtAge } from './formatters.js'
import { worstSource } from './intelStatus.js'

export default function StatusBar({
  system,
  onRunIngest,
  refreshInProgress,
  mode,
  setMode,
  lastUpdated,
  userMenu,
  onToggleSidebar,
  sidebarOpen,
}) {
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  const nvdAge = system?.last_nvd_sync_age_seconds
  const backupAge = system?.last_backup_age_seconds
  const backupThreshold = system?.backup_threshold_seconds || 43200
  const openCircuits = system?.open_circuit_count || 0
  const integrityOk = system?.db_integrity?.ok !== false
  const discordConfigured = system?.feeds?.sources?.['webhook.discord']?.last_success
  const discordFailed = system?.feeds?.sources?.['webhook.discord']?.circuit_open
  const telegramConfigured = system?.feeds?.sources?.['webhook.telegram']?.last_success
  const telegramFailed = system?.feeds?.sources?.['webhook.telegram']?.circuit_open
  const commit = system?.version?.commit

  function discordPillClass() {
    if (!discordConfigured) return 'pill-gray'
    return discordFailed ? 'pill-amber' : 'pill-green'
  }

  function telegramPillClass() {
    if (!telegramConfigured) return 'pill-gray'
    return telegramFailed ? 'pill-amber' : 'pill-green'
  }

  const worst = mode === 'analyst' ? worstSource(system) : null
  const updatedAgo = lastUpdated ? Math.max(0, Math.round((now - lastUpdated) / 1000)) : null

  return (
    <div className="admin-statusbar">
      <div className="admin-status-left" style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
        {onToggleSidebar && (
          <button
            type="button"
            className="admin-sidebar-toggle"
            onClick={onToggleSidebar}
            aria-label={sidebarOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={sidebarOpen}
          >
            {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
          </button>
        )}
        <Link to="/" className="admin-brand-link" title="Back to BRIEFR">
          <Shield size={15} strokeWidth={2.25} aria-hidden />
          BRIEFR
        </Link>
        <div className="sb-sep" />
        <span className={`admin-status-pill admin-status-pill--${mode}`}>
          {mode === 'analyst' ? 'Analyst' : 'Operator'}
        </span>
        <div className="sb-sep" />
        <div className="admin-mode-toggle-group">
          <div className="admin-mode-toggle" role="group" aria-label="Switch admin view mode">
            <button
              type="button"
              className={`admin-mode-toggle-btn ${mode === 'analyst' ? 'active' : ''}`}
              onClick={() => setMode('analyst')}
              title="Analyst view — CVE triage, simplified language, no destructive actions"
            >
              <Eye size={13} strokeWidth={2} /> Analyst
            </button>
            <button
              type="button"
              className={`admin-mode-toggle-btn ${mode === 'operator' ? 'active' : ''}`}
              onClick={() => setMode('operator')}
              title="Operator view — system management: restart, full ingest, purge, config"
            >
              <Wrench size={13} strokeWidth={2} /> Operator
            </button>
          </div>
        </div>
        <div className="sb-sep" />

        {mode === 'analyst' ? (
          <>
            <span className="sb-item">
              <span className="sb-label">CVEs</span>
              <span className="sb-value">{system?.cve_count?.toLocaleString() ?? '…'}</span>
            </span>
            <div className="sb-sep" />
            <span className="sb-item">
              <span className="sb-label">NVD feed</span>
              <span className={`sb-value ${nvdAge > 7200 ? 'sb-warn' : ''}`}>
                {nvdAge != null ? fmtAge(nvdAge) : '—'}
              </span>
            </span>
            {openCircuits > 0 && (
              <>
                <div className="sb-sep" />
                <span className="sb-item">
                  <span className="pill pill-amber">{worst || 'A source'} unavailable</span>
                </span>
              </>
            )}
          </>
        ) : (
          <>
            <span className="sb-item">
              <span className="sb-label">CVEs</span>
              <span className="sb-value">{system?.cve_count?.toLocaleString() ?? '…'}</span>
            </span>
            <div className="sb-sep" />
            <span className="sb-item">
              <span className="sb-label">NVD sync</span>
              <span className={`sb-value ${nvdAge > 7200 ? 'sb-warn' : ''}`}>
                {nvdAge != null ? fmtAge(nvdAge) : '—'}
              </span>
            </span>
            {backupAge != null && (
              <>
                <div className="sb-sep" />
                <span className="sb-item">
                  <span className="sb-label">Backup</span>
                  <span className={`sb-value ${backupAge > backupThreshold ? 'sb-warn' : ''}`}>
                    {fmtAge(backupAge)}
                  </span>
                </span>
              </>
            )}
            <div className="sb-sep" />
            <span className="sb-item">
              <span className="sb-label">Circuits</span>
              <span className={`sb-value ${openCircuits > 0 ? 'sb-warn' : ''}`}>{openCircuits} open</span>
            </span>
            <div className="sb-sep" />
            <span className="sb-item" title={integrityOk ? 'Last integrity check passed' : 'Last integrity check found a problem'}>
              <span className={`dot ${integrityOk ? 'dot-ok' : 'dot-error'}`} />
              <span className="sb-label">DB {integrityOk ? 'ok' : 'degraded'}</span>
            </span>
            <div className="sb-sep" />
            <span className="sb-item">
              <span className={`pill ${discordPillClass()}`} title="Discord webhook">Discord</span>
            </span>
            <span className="sb-item">
              <span className={`pill ${telegramPillClass()}`} title="Telegram webhook">Telegram</span>
            </span>
            {commit && (
              <>
                <div className="sb-sep" />
                <span className="sb-item">
                  <span className="sb-label mono" style={{ fontSize: '0.6875rem' }}>{commit.slice(0, 7) || 'dev'}</span>
                </span>
              </>
            )}
          </>
        )}
        {updatedAgo !== null && (
          <>
            <div className="sb-sep" />
            <span className="sb-item" title="Time since the status bar last refreshed from the backend">
              <Clock size={11} strokeWidth={2} />
              <span className="sb-label">Updated {updatedAgo}s ago</span>
            </span>
          </>
        )}
      </div>

      <div className="sb-actions">
        <ApiQueueIndicator apiQueue={system?.api_queue} className="admin-api-queue" />
        {userMenu}
        {mode === 'analyst' && (
          <>
            <button
              type="button"
              className="admin-btn admin-btn-ghost admin-btn--sm"
              onClick={onRunIngest}
              disabled={refreshInProgress}
              title="Pulls the latest CVEs, KEV entries, and EPSS scores from every source right now"
            >
              {refreshInProgress ? (
                <><span className="admin-spinner" /> Refreshing…</>
              ) : (
                <><RefreshCw size={13} strokeWidth={2} /> Refresh all sources</>
              )}
            </button>
            <HelpTip text="Pulls the latest CVEs, KEV entries, and EPSS scores from every configured source right now, instead of waiting for the normal schedule." />
          </>
        )}
      </div>
    </div>
  )
}
