import { useRef } from 'react'
import './SessionLockOverlay.css'

export default function SessionLockOverlay({ onLoadProfile }) {
  const fileRef = useRef(null)

  function handlePick() {
    fileRef.current?.click()
  }

  async function handleFile(e) {
    const file = e.target.files?.[0]
    if (file && onLoadProfile) {
      await onLoadProfile(file)
    }
    e.target.value = ''
  }

  return (
    <div className="session-lock-overlay" role="dialog" aria-modal="true">
      <div className="session-lock-inner">
        <p className="session-lock-logo">BRIEFR</p>
        <p className="session-lock-cleared mono">Session cleared for security</p>
        <p className="session-lock-hint mono">Reload your profile to continue</p>
        <button type="button" className="session-lock-load mono" onClick={handlePick}>
          Load Profile
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          className="session-lock-file"
          tabIndex={-1}
          onChange={handleFile}
        />
      </div>
    </div>
  )
}
