import Tooltip from './ui/Tooltip.jsx'
import './ExplainTip.css'

/**
 * Discoverable explanation for badges, pills, and filter controls (PRODUCT.md §1).
 */
export default function ExplainTip({ text, label = 'Explain' }) {
  if (!text) return null
  return (
    <Tooltip
      text={text}
      asChild
      trigger="hover-focus"
      className="explain-tip-wrap"
      bubbleClassName="explain-tip-bubble"
      maxWidth={220}
    >
      <button
        type="button"
        className="explain-tip-btn mono"
        aria-label={label}
      >
        ?
      </button>
    </Tooltip>
  )
}
