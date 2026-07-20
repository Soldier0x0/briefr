import { useState } from 'react'
import { RefreshCw, RotateCw, Hourglass } from 'lucide-react'
import DangerZone from './DangerZone.jsx'
import ConfirmModal from './ConfirmModal.jsx'
import HelpTip from './HelpTip.jsx'

/** Destructive ingest/restart controls — bottom of operator pages only. */
export default function OperatorSystemActions({
  onRunIngest,
  onRestart,
  onDrainRestart,
  refreshInProgress = false,
}) {
  const [confirmRestart, setConfirmRestart] = useState(null)

  return (
    <>
      {confirmRestart && (
        <ConfirmModal
          actionId={confirmRestart === 'drain' ? 'system.restart.drain' : 'system.restart'}
          title={confirmRestart === 'drain' ? 'Finish jobs, then restart' : 'Restart backend now?'}
          message={
            confirmRestart === 'drain'
              ? 'Wait for all running jobs to finish, then shut the backend down gracefully (systemd will restart it).'
              : 'Stops the backend immediately — systemd restarts it within seconds. In-flight jobs may be interrupted.'
          }
          confirmWord="restart"
          onConfirm={() => {
            setConfirmRestart(null)
            if (confirmRestart === 'drain') onDrainRestart?.()
            else onRestart?.()
          }}
          onCancel={() => setConfirmRestart(null)}
        />
      )}
      <DangerZone title="System controls">
        <p style={{ fontSize: '0.8125rem', color: 'var(--text2)', margin: '0 0 0.75rem', lineHeight: 1.5 }}>
          Heavy operations — only use when you intentionally want to refresh all intel sources or restart the backend process.
        </p>
        <div className="admin-action-bar" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
          <button
            className="admin-btn admin-btn-warn"
            onClick={onRunIngest}
            disabled={refreshInProgress}
            style={{ fontSize: '0.8125rem' }}
          >
            {refreshInProgress
              ? <><span className="admin-spinner" /> Running full ingest…</>
              : <><RefreshCw size={13} strokeWidth={2} /> Run full ingest</>}
          </button>
          <HelpTip text="Pulls fresh data from every configured source — NVD, KEV, EPSS, MITRE/ATLAS, OTX, etc." />
          <button
            className="admin-btn admin-btn-danger"
            onClick={() => setConfirmRestart('immediate')}
            style={{ fontSize: '0.8125rem' }}
          >
            <RotateCw size={13} strokeWidth={2} /> Restart now
          </button>
          <button
            className="admin-btn admin-btn-ghost"
            onClick={() => setConfirmRestart('drain')}
            style={{ fontSize: '0.8125rem' }}
          >
            <Hourglass size={12} strokeWidth={2} /> Finish jobs, then restart
          </button>
          <HelpTip text="Waits for in-flight scheduler jobs to finish before restarting — safer during active syncs. Does not abort running work." />
        </div>
      </DangerZone>
    </>
  )
}
