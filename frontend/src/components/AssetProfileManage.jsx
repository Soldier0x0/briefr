import { useRef } from 'react'
import './AssetWarning.css'

export default function AssetProfileManage({
  onUpdate,
  onUpload,
  onKeep,
  onClose,
}) {
  const fileRef = useRef(null)

  function handlePick() {
    fileRef.current?.click()
  }

  async function handleFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''
    if (onUpload) {
      try {
        await onUpload(file)
      } catch {
        alert('Failed to load profile: Invalid or corrupted file.')
      }
    }
  }

  return (
    <div className="asset-modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="asset-modal asset-warning"
        role="dialog"
        aria-modal="true"
        aria-labelledby="asset-manage-title"
        onClick={e => e.stopPropagation()}
      >
        <pre id="asset-manage-title" className="asset-warning-text mono">{`// PROFILE ALREADY LOADED

You have an active asset profile in this session.

Update your profile to change operating systems, applications,
or environment details. Upload a saved profile file to replace
the current one. Keep current profile to continue without changes.`}</pre>
        <div className="asset-warning-actions">
          <button type="button" className="asset-btn asset-btn-primary mono" onClick={onUpdate}>
            Update my profile
          </button>
          <button type="button" className="asset-btn asset-btn-primary mono" onClick={handlePick}>
            Upload a different profile
          </button>
          <button type="button" className="asset-btn asset-btn-ghost mono" onClick={onKeep}>
            Keep current profile
          </button>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          className="asset-file-input"
          tabIndex={-1}
          onChange={handleFile}
        />
      </div>
    </div>
  )
}
