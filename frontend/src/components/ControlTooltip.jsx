import Tooltip from './ui/Tooltip.jsx'
import './ControlTooltip.css'

/**
 * Accessible tooltip on the control itself.
 * Default trigger is hover-only so filter buttons do not stick open after click.
 */
export default function ControlTooltip({ text, children, className = '', trigger = 'hover' }) {
  if (!text) return children

  return (
    <Tooltip
      text={text}
      asChild
      trigger={trigger}
      className={`control-tooltip-wrap ${className}`.trim()}
      bubbleClassName="control-tooltip-bubble"
      maxWidth={240}
    >
      {children}
    </Tooltip>
  )
}
