import * as AlertDialog from '@radix-ui/react-alert-dialog'
import Button from './Button.jsx'

/**
 * Radix AlertDialog primitive (E3-4) — simple destructive confirmations.
 * Typed confirm gates should use ConfirmModal (Dialog-based).
 */
export default function UiAlertDialog({
  open,
  onOpenChange,
  title,
  description,
  cancelLabel = 'Cancel',
  confirmLabel = 'Confirm',
  onConfirm,
  className = '',
  overlayClassName = '',
}) {
  const overlayClasses = ['ui-modal-overlay', overlayClassName].filter(Boolean).join(' ')
  const dialogClasses = ['ui-modal', 'ui-modal--sm', className].filter(Boolean).join(' ')

  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className={overlayClasses} />
        <AlertDialog.Content className={dialogClasses}>
          {title && (
            <AlertDialog.Title className="ui-modal-title">{title}</AlertDialog.Title>
          )}
          {description && (
            <AlertDialog.Description className="ui-confirm-message">
              {description}
            </AlertDialog.Description>
          )}
          <div className="ui-modal-footer">
            <AlertDialog.Cancel asChild>
              <Button variant="ghost">{cancelLabel}</Button>
            </AlertDialog.Cancel>
            <AlertDialog.Action asChild>
              <Button variant="danger" onClick={onConfirm}>
                {confirmLabel}
              </Button>
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}
