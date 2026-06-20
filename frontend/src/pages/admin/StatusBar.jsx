import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import ConfirmModal from './shared/ConfirmModal.jsx'
import { fmtAge } from './formatters.js'

export default function StatusBar({ system, onRunIngest, onRestart, onDrainRestart, refreshInProgress }) {
  const [restartMenu, setRestartMenu] = useState(false)
  const [menuPos, setMenuPos] = useState(null)
  const [confirmRestart, setConfirmRestart] = useState(null) // null | 'immediate' | 'drain'
  const menuRef = useRef(null)
  const arrowRef = useRef(null)

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
          confirmWord={confirmRestart === 'drain' ? 'restart' : undefined}
          onConfirm={() => {
            setConfirmRestart(null)
            if (confirmRestart === 'drain') onDrainRestart()
            else onRestart()
          }}
          onCancel={() => setConfirmRestart(null)}
        />
      )}
      <div className="admin-statusbar">
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
        <span className="sb-item">
          <span className={`dot ${integrityOk ? 'dot-ok' : 'dot-error'}`} />
          <span className="sb-label">DB {integrityOk ? 'ok' : 'degraded'}</span>
        </span>
        <div className="sb-sep" />
        <span className="sb-item">
          <span className={`pill ${discordPillClass()}`}>Discord</span>
        </span>
        <span className="sb-item">
          <span className={`pill ${telegramPillClass()}`}>Telegram</span>
        </span>
        {commit && (
          <>
            <div className="sb-sep" />
            <span className="sb-item">
              <span className="sb-label mono" style={{ fontSize: '0.6875rem' }}>{commit.slice(0, 7) || 'dev'}</span>
            </span>
          </>
        )}
        <div className="sb-actions">
          <button
            className="admin-btn admin-btn-warn"
            onClick={onRunIngest}
            disabled={refreshInProgress}
            style={{ fontSize: '0.75rem' }}
          >
            {refreshInProgress ? <><span className="admin-spinner" /> Running…</> : 'Run full ingest'}
          </button>
          <div className="admin-split-btn" ref={menuRef}>
            <button
              className="admin-btn admin-btn-ghost admin-split-btn-main"
              onClick={() => setConfirmRestart('immediate')}
              style={{ fontSize: '0.75rem' }}
            >
              Restart now
            </button>
            <button
              ref={arrowRef}
              className="admin-btn admin-btn-ghost admin-split-btn-arrow"
              onClick={toggleRestartMenu}
              aria-label="Restart options"
              style={{ fontSize: '0.75rem' }}
            >▾</button>
            {restartMenu && menuPos && createPortal(
              <div
                className="admin-split-menu"
                ref={menuRef}
                style={{ top: menuPos.top, right: menuPos.right }}
              >
                <button className="admin-split-menu-item" onClick={() => { setRestartMenu(false); setConfirmRestart('immediate') }}>Restart now</button>
                <button className="admin-split-menu-item" onClick={() => { setRestartMenu(false); setConfirmRestart('drain') }}>Drain then restart</button>
              </div>,
              document.body
            )}
          </div>
        </div>
      </div>
    </>
  )
}
