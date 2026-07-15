/**
 * Fixed-height chart container (E7-5). Prevents unbounded chart growth (UI-BUG-1).
 */
export default function ChartShell({
  height = 200,
  ariaLabel,
  className = '',
  children,
}) {
  return (
    <div
      className={`chart-shell${className ? ` ${className}` : ''}`}
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
    >
      {children}
    </div>
  )
}
