/**
 * @param {object} props
 * @param {'text'|'block'} [props.variant='text']
 * @param {string} [props.className]
 * @param {string} [props.style]
 */
export default function Skeleton({ variant = 'text', className = '', style, ...rest }) {
  const classes = [
    'ui-skeleton',
    variant === 'block' ? 'ui-skeleton--block' : 'ui-skeleton--text',
    className,
  ].filter(Boolean).join(' ')

  return (
    <span
      className={classes}
      role="status"
      aria-label="Loading"
      style={style}
      {...rest}
    />
  )
}
