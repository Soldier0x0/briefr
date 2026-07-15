import { useId, useRef } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import useModalLayer from '../../hooks/useModalLayer.js'

/**
 * Radix-backed dialog primitive (E3-4). Preserves the legacy Modal API.
 * @param {object} props
 * @param {boolean} props.open
 * @param {() => void} props.onClose
 * @param {string} [props.title]
 * @param {string} [props.titleId]
 * @param {boolean} [props.busy=false]
 * @param {'default'|'sm'|'lg'} [props.size='default']
 * @param {React.ReactNode} [props.footer]
 * @param {string} [props.className]
 * @param {string} [props.overlayClassName]
 * @param {React.ReactNode} [props.children]
 */
export default function Modal({
  open,
  onClose,
  title,
  titleId,
  busy = false,
  size = 'default',
  footer,
  className = '',
  overlayClassName = '',
  children,
  ...rest
}) {
  const contentRef = useRef(null)
  const generatedId = useId()
  const headingId = titleId || generatedId

  useModalLayer(open, contentRef, { trackDepth: true, trapFocus: false })

  const dialogClasses = [
    'ui-modal',
    size !== 'default' ? `ui-modal--${size}` : '',
    className,
  ].filter(Boolean).join(' ')

  const overlayClasses = ['ui-modal-overlay', overlayClassName].filter(Boolean).join(' ')

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next && !busy) onClose()
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className={overlayClasses} />
        <Dialog.Content
          ref={contentRef}
          className={dialogClasses}
          aria-labelledby={title ? headingId : undefined}
          onPointerDownOutside={(event) => {
            if (busy) event.preventDefault()
          }}
          onInteractOutside={(event) => {
            if (busy) event.preventDefault()
          }}
          onEscapeKeyDown={(event) => {
            if (busy) event.preventDefault()
          }}
          {...rest}
        >
          {title && (
            <Dialog.Title id={headingId} className="ui-modal-title">
              {title}
            </Dialog.Title>
          )}
          <div className="ui-modal-body">{children}</div>
          {footer && <div className="ui-modal-footer">{footer}</div>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
