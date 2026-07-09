/**
 * @param {object} props
 * @param {string} [props.title='No data']
 * @param {React.ReactNode} [props.action]
 * @param {string} [props.className]
 */
export default function EmptyState({ title = 'No data', action, className = '', ...rest }) {
  return (
    <div className={`ui-empty ${className}`.trim()} {...rest}>
      <span>{title}</span>
      {action}
    </div>
  )
}
