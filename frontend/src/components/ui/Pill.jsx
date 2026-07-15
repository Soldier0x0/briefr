/**
 * Toggle chip / filter pill primitive (E3-7).
 * @param {object} props
 * @param {boolean} [props.active]
 * @param {string} [props.className]
 * @param {React.ReactNode} [props.children]
 * @param {() => void} [props.onClick]
 */
export default function Pill({
  active = false,
  className = '',
  children,
  onClick,
  ...rest
}) {
  return (
    <button
      type="button"
      className={[
        'ui-pill',
        'filter-chip',
        active ? 'active' : '',
        className,
      ].filter(Boolean).join(' ')}
      aria-pressed={active}
      onClick={onClick}
      {...rest}
    >
      {children}
    </button>
  )
}

/**
 * @param {object} props
 * @param {string} [props.className]
 * @param {React.ReactNode} [props.children]
 */
export function PillGroup({ className = '', children, ...rest }) {
  return (
    <div className={['ui-pill-group', 'admin-filter-chips', className].filter(Boolean).join(' ')} {...rest}>
      {children}
    </div>
  )
}
