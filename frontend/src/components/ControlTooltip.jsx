import { cloneElement, useId } from 'react'
import './ControlTooltip.css'

/**
 * Accessible tooltip on the control itself (hover + keyboard focus).
 * Reuses ExplainTip bubble styling without a separate "?" button.
 */
export default function ControlTooltip({ text, children, className = '' }) {
  const id = useId()
  if (!text) return children

  const child = cloneElement(children, {
    'aria-describedby': [children.props['aria-describedby'], id].filter(Boolean).join(' ') || id,
  })

  return (
    <span className={`control-tooltip-wrap ${className}`.trim()}>
      {child}
      <span role="tooltip" id={id} className="control-tooltip-bubble">
        {text}
      </span>
    </span>
  )
}
