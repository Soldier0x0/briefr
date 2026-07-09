import { useEffect, useState } from 'react'
import { Modal, Button } from './ui/index.js'
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

  useEffect(() => {
    if (!open) return
    setAnalystName('')
  }, [open])

  function handleSubmit(e) {
    e.preventDefault()
    onConfirm({ analystName: analystName.trim() })
  }

  const footer = (
    <>
      <Button variant="ghost" onClick={onCancel} disabled={busy}>
        Cancel
      </Button>
      <Button variant="primary" type="submit" form="pdf-export-form" busy={busy} busyLabel={busyLabel}>
        Generate PDF
      </Button>
    </>
  )

  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      busy={busy}
      footer={footer}
      className="pdf-modal"
      overlayClassName="pdf-modal-overlay"
    >
      <p className="pdf-modal-sub">
        Reports use publicly available intelligence only. Analyst name is optional and is not stored.
      </p>

      {error && (
        <p className="pdf-modal-error mono" role="alert">
          {error}
        </p>
      )}

      <form id="pdf-export-form" onSubmit={handleSubmit}>
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
      </form>
    </Modal>
  )
}
