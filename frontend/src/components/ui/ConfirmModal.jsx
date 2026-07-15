import { useEffect, useRef, useState } from 'react'
import Modal from './Modal.jsx'
import UiAlertDialog from './AlertDialog.jsx'
import Button from './Button.jsx'

/**
 * @param {object} props
 * @param {boolean} [props.open=true]
 * @param {string} [props.title]
 * @param {string} [props.message]
 * @param {string} [props.confirmWord]
 * @param {(value: string) => void} props.onConfirm
 * @param {() => void} props.onCancel
 * @param {() => void} [props.onClose]
 * @param {string} [props.confirmLabel='Confirm']
 * @param {string} [props.cancelLabel='Cancel']
 * @param {string} [props.className]
 * @param {string} [props.overlayClassName]
 */
export default function ConfirmModal({
  open = true,
  title,
  message,
  confirmWord,
  onConfirm,
  onCancel,
  onClose,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  className = '',
  overlayClassName = '',
}) {
  const [input, setInput] = useState('')
  const stateRef = useRef({ input, confirmWord, onCancel, onConfirm, onClose })
  const close = onClose || onCancel

  stateRef.current = { input, confirmWord, onCancel, onConfirm, onClose: close }

  useEffect(() => {
    if (!open) setInput('')
  }, [open])

  useEffect(() => {
    if (!open || !confirmWord) return undefined
    function onKey(e) {
      const { input, confirmWord, onConfirm, onClose: dismiss } = stateRef.current
      if (e.key === 'Escape') dismiss()
      else if (e.key === 'Enter' && input === confirmWord) onConfirm(input)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, confirmWord])

  const word = confirmWord || ''
  const canConfirm = !word || input === word

  if (!word) {
    return (
      <UiAlertDialog
        open={open}
        onOpenChange={(next) => { if (!next) close() }}
        title={title}
        description={message}
        cancelLabel={cancelLabel}
        confirmLabel={confirmLabel}
        onConfirm={() => onConfirm('')}
        className={className}
        overlayClassName={overlayClassName}
      />
    )
  }

  const footer = (
    <>
      <Button variant="ghost" onClick={close}>
        {cancelLabel}
      </Button>
      <Button
        variant="danger"
        onClick={() => onConfirm(input)}
        disabled={!canConfirm}
      >
        {confirmLabel}
      </Button>
    </>
  )

  return (
    <Modal
      open={open}
      onClose={close}
      title={title}
      footer={footer}
      className={className}
      overlayClassName={overlayClassName}
    >
      {message && <p className="ui-confirm-message">{message}</p>}
      {word && (
        <div className="ui-confirm-gate">
          <label className="ui-confirm-label" htmlFor="ui-confirm-input">
            Type <code className="mono">{word}</code> to confirm
          </label>
          <input
            id="ui-confirm-input"
            className="ui-confirm-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={word}
            autoFocus
          />
        </div>
      )}
    </Modal>
  )
}
