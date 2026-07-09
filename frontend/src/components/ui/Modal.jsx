import { useEffect, useId, useRef } from 'react'
import useModalLayer from '../../hooks/useModalLayer.js'

/**
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
  const dialogRef = useRef(null)
  const generatedId = useId()
  const headingId = titleId || generatedId

  useModalLayer(open, dialogRef, { trackDepth: true })

  useEffect(() => {
    if (!open) return undefined
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    function onKey(e) {
      if (e.key === 'Escape' && !busy) onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, busy, onClose])

  if (!open) return null

  const dialogClasses = [
    'ui-modal',
    size !== 'default' ? `ui-modal--${size}` : '',
    className,
  ].filter(Boolean).join(' ')

  const overlayClasses = ['ui-modal-overlay', overlayClassName].filter(Boolean).join(' ')

  return (
    <div
      className={overlayClasses}
      onClick={busy ? undefined : onClose}
      role="presentation"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? headingId : undefined}
        className={dialogClasses}
        onClick={e => e.stopPropagation()}
        tabIndex={-1}
        {...rest}
      >
        {title && (
          <h2 id={headingId} className="ui-modal-title">
            {title}
          </h2>
        )}
        <div className="ui-modal-body">{children}</div>
        {footer && <div className="ui-modal-footer">{footer}</div>}
      </div>
    </div>
  )
}
