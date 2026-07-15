import Tooltip from './Tooltip.jsx'

/**
 * Long URL / reference tooltips (E2-4): portaled, viewport-clamped, word-wrapped.
 */
export default function ReferenceTooltip({ text, children, className = '' }) {
  if (!text) return children

  return (
    <Tooltip
      text={text}
      asChild
      trigger="hover-focus"
      className={`reference-tooltip-wrap ${className}`.trim()}
      bubbleClassName="reference-tooltip-bubble"
      maxWidth={Math.min(420, typeof window !== 'undefined' ? window.innerWidth - 32 : 420)}
    >
      {children}
    </Tooltip>
  )
}
