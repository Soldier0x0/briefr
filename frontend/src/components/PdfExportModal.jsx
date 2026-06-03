import { useEffect, useRef, useState } from 'react'
import { TLP_OPTIONS } from '../utils/pdfReport.js'
import './PdfExportModal.css'

export default function PdfExportModal({
  open,
  title = 'Generate PDF report',
  onConfirm,
  onCancel,
  busy = false,
}) {
  const [tlp, setTlp] = useState('WHITE')
  const [analystName, setAnalystName] = useState('')
  const dialogRef = useRef(null)

  useEffect(() => {
    if (!open) return
    setTlp('WHITE')
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
    onConfirm({ tlp, analystName: analystName.trim() })
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
          Choose TLP classification for the document. Analyst name is optional and is not stored.
        </p>

        <form onSubmit={handleSubmit}>
          <fieldset className="pdf-modal-fieldset">
            <legend className="pdf-modal-legend mono">Classification</legend>
            <div className="pdf-tlp-options" role="radiogroup" aria-label="TLP classification">
              {TLP_OPTIONS.map(opt => (
                <label
                  key={opt.id}
                  className={`pdf-tlp-option${tlp === opt.id ? ' selected' : ''}`}
                  style={opt.color ? { '--tlp-preview': `rgb(${opt.color.join(',')})` } : undefined}
                >
                  <input
                    type="radio"
                    name="tlp"
                    value={opt.id}
                    checked={tlp === opt.id}
                    onChange={() => setTlp(opt.id)}
                    disabled={busy}
                  />
                  <span className="pdf-tlp-swatch" aria-hidden="true" />
                  <span className="mono">{opt.label}</span>
                </label>
              ))}
            </div>
          </fieldset>

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
              {busy ? 'Generating…' : 'Generate PDF'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
