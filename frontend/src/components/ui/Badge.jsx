import Tooltip from './Tooltip.jsx'

/**
 * @param {object} props
 * @param {'neutral'|'info'|'warn'|'danger'|'success'} [props.variant='neutral']
 * @param {string} props.explain - Required tooltip text (PRODUCT.md principle 1).
 * @param {string} [props.className]
 * @param {React.ReactNode} [props.children]
 */
export default function Badge({
  variant = 'neutral',
  explain,
  className = '',
  children,
  ...rest
}) {
  const classes = ['ui-badge', `ui-badge--${variant}`, className].filter(Boolean).join(' ')

  return (
    <Tooltip text={explain}>
      <span className={classes} {...rest}>
        {children}
      </span>
    </Tooltip>
  )
}
