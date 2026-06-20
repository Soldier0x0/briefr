import { useEffect, useRef, useState } from 'react'
import useModalLayer from '../hooks/useModalLayer.js'
import './PdfExportModal.css'

export default function PdfExportModal({
  open,
  title = 'Generate PDF report',
  onConfirm,
  onCancel,
  busy = false,
  busyLabel = 'Generating summary...',
  error = null,
}) {
  const [analystName, setAnalystName] = useState('')
  const dialogRef = useRef(null)

  // Owns its Escape handling → registers depth so the global handler stands
  // down; traps Tab inside the dialog and restores focus on close.
  useModalLayer(open, dialogRef, { trackDepth: true })

  useEffect(() => {
    if (!open) return
    setAnalystName('')
    function onKey(e) {
      if (e.key === 'Escape' && !busy) onCancel()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, busy, onCancel])

  if (!open) return null

  function handleSubmit(e) {
    e.preventDefault()
    onConfirm({ analystName: analystName.trim() })
  }

  return (
    <div className="pdf-modal-overlay" onClick={busy ? undefined : onCancel} role="presentation">
      <div
        className="pdf-modal"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="pdf-modal-title"
        onClick={e => e.stopPropagation()}
      >
        <h2 id="pdf-modal-title" className="pdf-modal-title mono">{title}</h2>
        <p className="pdf-modal-sub">
          Reports use publicly available intelligence only. Analyst name is optional and is not stored.
        </p>

        {error && (
          <p className="pdf-modal-error mono" role="alert">
            {error}
          </p>
        )}

        <form onSubmit={handleSubmit}>
          <label className="pdf-modal-label mono" htmlFor="pdf-analyst-name">
            Analyst name (optional)
          </label>
          <input
            id="pdf-analyst-name"
            className="pdf-modal-input"
            type="text"
            value={analystName}
            onChange={e => setAnalystName(e.target.value)}
            placeholder="e.g. Security Operations"
            maxLength={80}
            disabled={busy}
            autoComplete="off"
          />

          <div className="pdf-modal-actions">
            <button type="button" className="pdf-modal-btn" onClick={onCancel} disabled={busy}>
              Cancel
            </button>
            <button type="submit" className="pdf-modal-btn pdf-modal-btn-primary" disabled={busy}>
              {busy ? busyLabel : 'Generate PDF'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
