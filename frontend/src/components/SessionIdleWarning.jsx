import { downloadProfileJson } from '../utils/assetProfileIo.js'
import './SessionIdleWarning.css'

export default function SessionIdleWarning({ profile, onDismiss }) {
  function handleExport() {
    if (profile) downloadProfileJson(profile)
  }

  return (
    <div className="session-idle-warning" role="alertdialog" aria-labelledby="session-idle-title">
      <div className="session-idle-inner">
        <p id="session-idle-title" className="session-idle-title mono">My Stack session locking soon</p>
        <p className="session-idle-body mono">
          In about 5 minutes your My Stack will clear for security. Export a copy now if you have not saved one —
          otherwise reload your file after the session locks.
        </p>
        <div className="session-idle-actions">
          <button type="button" className="session-idle-export mono" onClick={handleExport}>
            Export My Stack
          </button>
          <button type="button" className="session-idle-dismiss mono" onClick={onDismiss}>
            Dismiss
          </button>
        </div>
      </div>
    </div>
  )
}
