/**
 * Raised surface primitive (E3-7). Composes admin-card layout during migration.
 * @param {object} props
 * @param {string} [props.className]
 * @param {React.ReactNode} [props.children]
 */
export function Card({ className = '', children, ...rest }) {
  return (
    <div className={['ui-card', 'admin-card', className].filter(Boolean).join(' ')} {...rest}>
      {children}
    </div>
  )
}

/**
 * @param {object} props
 * @param {string} [props.className]
 * @param {React.ReactNode} [props.children]
 */
export function CardTitle({ className = '', children, ...rest }) {
  return (
    <div className={['ui-card-title', 'admin-card-title', className].filter(Boolean).join(' ')} {...rest}>
      {children}
    </div>
  )
}

/**
 * @param {object} props
 * @param {string} [props.className]
 * @param {React.ReactNode} [props.children]
 */
export function CardBody({ className = '', children, ...rest }) {
  return (
    <div className={['ui-card-body', className].filter(Boolean).join(' ')} {...rest}>
      {children}
    </div>
  )
}

export default Card
