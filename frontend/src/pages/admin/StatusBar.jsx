import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { Eye, Wrench, RefreshCw, RotateCw, Hourglass, ChevronDown, Clock } from 'lucide-react'
import ConfirmModal from './shared/ConfirmModal.jsx'
import HelpTip from './shared/HelpTip.jsx'
import { fmtAge } from './formatters.js'
import { worstSource } from './intelStatus.js'

export default function StatusBar({ system, onRunIngest, onRestart, onDrainRestart, refreshInProgress, mode, setMode, lastUpdated, userMenu }) {
  const [restartMenu, setRestartMenu] = useState(false)
  const [menuPos, setMenuPos] = useState(null)
  const [confirmRestart, setConfirmRestart] = useState(null) // null | 'immediate' | 'drain'
  const [now, setNow] = useState(Date.now())
  const menuRef = useRef(null)
  const arrowRef = useRef(null)

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  function handleModeClick(next) {
    setMode(next)
  }

  useEffect(() => {
    function onDown(e) {
      if (
        restartMenu &&
        menuRef.current &&
        !menuRef.current.contains(e.target) &&
        !arrowRef.current?.contains(e.target)
      ) {
        setRestartMenu(false)
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [restartMenu])

  function toggleRestartMenu() {
    if (!restartMenu && arrowRef.current) {
      const rect = arrowRef.current.getBoundingClientRect()
      setMenuPos({ top: rect.bottom + 4, right: window.innerWidth - rect.right })
    }
    setRestartMenu(v => !v)
  }

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
  const updatedAgoEl = updatedAgo !== null ? (
    <>
      <div className="sb-sep" />
      <span className="sb-item" title="Time since the status bar last refreshed from the backend">
        <Clock size={11} strokeWidth={2} />
        <span className="sb-label">Updated {updatedAgo}s ago</span>
      </span>
    </>
  ) : null

  return (
    <>
      {confirmRestart && (
        <ConfirmModal
          actionId={confirmRestart === 'drain' ? 'system.restart.drain' : 'system.restart'}
          title={confirmRestart === 'drain' ? 'Drain then restart' : 'Restart now?'}
          message={
            confirmRestart === 'drain'
              ? 'Wait for all running jobs to finish, then shut the backend down gracefully (systemd will restart it).'
              : undefined
          }
          confirmWord="restart"
          onConfirm={() => {
            setConfirmRestart(null)
            if (confirmRestart === 'drain') onDrainRestart()
            else onRestart()
          }}
          onCancel={() => setConfirmRestart(null)}
        />
      )}
      <div className="admin-statusbar">
        <Link to="/" className="admin-brand-link mono" title="Back to BRIEFR">
          BRIEFR
        </Link>
        <div className="sb-sep" />
        <div className="admin-mode-toggle-group">
          <span className="admin-mode-toggle-label">VIEW</span>
          <div className="admin-mode-toggle" role="group" aria-label="Switch admin view mode">
            <button
              className={`admin-mode-toggle-btn ${mode === 'analyst' ? 'active' : ''}`}
              onClick={() => handleModeClick('analyst')}
              title="Analyst view — CVE triage, simplified language, no destructive actions"
            ><Eye size={13} strokeWidth={2} /> Analyst</button>
            <button
              className={`admin-mode-toggle-btn ${mode === 'operator' ? 'active' : ''}`}
              onClick={() => handleModeClick('operator')}
              title="Operator view — system management: restart, full ingest, purge, config"
            ><Wrench size={13} strokeWidth={2} /> Operator</button>
          </div>
        </div>
        <div className="sb-sep" />

        <div className="admin-statusbar-scroll">
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
            {updatedAgoEl}
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
              <span className={`sb-value ${openCircuits > 0 ? 'sb-warn' : ''}`}>{openCircuits > 0 ? `${openCircuits} tripped` : 'OK'}</span>
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
                <span className="sb-item" title={`Deployed build ${commit} — git commit short hash for support and rollback`}>
                  <HelpTip text="Short git commit of the running backend build. Match this to the version in Admin → Overview after deploy." />
                  <span className="sb-label mono">Build {commit.slice(0, 7)}</span>
                </span>
              </>
            )}
            {updatedAgoEl}
          </>
        )}
        </div>

        <div className="sb-actions">
          {userMenu}
          {mode === 'analyst' && (
            <>
              <button
                className="admin-btn admin-btn-ghost"
                onClick={onRunIngest}
                disabled={refreshInProgress}
                style={{ fontSize: '0.8125rem' }}
                title="Pulls the latest CVEs, KEV entries, and EPSS scores from every source right now"
              >
                {refreshInProgress ? <><span className="admin-spinner" /> Refreshing…</> : <><RefreshCw size={13} strokeWidth={2} /> Refresh all sources</>}
              </button>
              <HelpTip text="Pulls the latest CVEs, KEV entries, and EPSS scores from every configured source right now, instead of waiting for the normal schedule." />
            </>
          )}
        </div>
      </div>
    </>
  )
}
