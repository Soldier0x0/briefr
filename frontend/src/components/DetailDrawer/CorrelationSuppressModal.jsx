import { useEffect, useState } from 'react'
import { Select } from '../ui/index.js'
import { SUPPRESSION_REASONS, suppressionDialogCopy } from '../../utils/correlationPresentation.js'
import './CorrelationSuppressModal.css'

export default function CorrelationSuppressModal({
  open,
  body,
  cveId,
  peerCve,
  onCancel,
  onConfirm,
  submitting,
}) {
  const [reason, setReason] = useState('shared_hosting')
  const copy = body ? suppressionDialogCopy(body, cveId, peerCve) : null

  useEffect(() => {
    if (open) {
      setReason('shared_hosting')
    }
  }, [open])

  if (!open || !copy) return null

  function handleSubmit(e) {
    e.preventDefault()
    const reasonLabel = SUPPRESSION_REASONS.find(r => r.id === reason)?.label || reason
    onConfirm?.({ ...body, reason: reasonLabel })
  }

  return (
    <div className="corr-suppress-overlay" role="presentation" onClick={onCancel}>
      <div
        className="corr-suppress-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="corr-suppress-title"
        onClick={e => e.stopPropagation()}
      >
        <h2 id="corr-suppress-title" className="corr-suppress-title mono">
          {copy.title}
        </h2>
        <p className="corr-suppress-body">{copy.body}</p>
        <p className="corr-suppress-note">{copy.note}</p>

        <form onSubmit={handleSubmit}>
          <label htmlFor="corr-suppress-reason" className="corr-suppress-reason-label mono">
            Reason
          </label>
          <Select
            id="corr-suppress-reason"
            className="corr-suppress-reason mono"
            value={reason}
            onChange={setReason}
            options={SUPPRESSION_REASONS.map(r => ({ value: r.id, label: r.label }))}
          />

          <div className="corr-suppress-actions">
            <button
              type="button"
              className="corr-suppress-cancel mono"
              onClick={onCancel}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="corr-suppress-confirm mono"
              disabled={submitting}
            >
              {submitting ? 'Hiding…' : 'Hide this link'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
