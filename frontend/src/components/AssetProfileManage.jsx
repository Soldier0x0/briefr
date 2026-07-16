import { useRef } from 'react'
import AssetRememberToggle from './AssetRememberToggle.jsx'
import './AssetWarning.css'

export default function AssetProfileManage({
  rememberOnServer,
  onRememberChange,
  showRememberToggle = false,
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
        alert('Failed to load My Stack: Invalid or corrupted file.')
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
        <pre id="asset-manage-title" className="asset-warning-text mono">{`// MY STACK ALREADY LOADED

You have an active My Stack in this session. Update My Stack to change operating systems, applications, or environment details. Upload a saved file to replace the current one, or keep current to continue without changes.`}</pre>
        {showRememberToggle && (
          <AssetRememberToggle
            enabled={rememberOnServer}
            onChange={(v) => { void onRememberChange?.(v) }}
          />
        )}
        <div className="asset-warning-actions">
          <button type="button" className="asset-btn asset-btn-primary mono" onClick={onUpdate}>
            Update My Stack
          </button>
          <button type="button" className="asset-btn asset-btn-primary mono" onClick={handlePick}>
            Upload a different file
          </button>
          <button type="button" className="asset-btn asset-btn-ghost mono" onClick={onKeep}>
            Keep current My Stack
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
