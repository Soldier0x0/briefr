import './ui.css'

/**
 * @param {object} props
 * @param {'primary'|'ghost'|'danger'} [props.variant='ghost']
 * @param {'default'|'sm'} [props.size='default']
 * @param {boolean} [props.busy=false]
 * @param {string} [props.busyLabel]
 * @param {string} [props.className]
 * @param {React.ReactNode} [props.children]
 */
export default function Button({
  variant = 'ghost',
  size = 'default',
  busy = false,
  busyLabel,
  className = '',
  children,
  disabled,
  type = 'button',
  ...rest
}) {
  const classes = [
    'ui-btn',
    variant !== 'ghost' ? `ui-btn--${variant}` : 'ui-btn--ghost',
    size === 'sm' ? 'ui-btn--sm' : '',
    className,
  ].filter(Boolean).join(' ')

  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...rest}
    >
      {busy && busyLabel ? busyLabel : children}
    </button>
  )
}
