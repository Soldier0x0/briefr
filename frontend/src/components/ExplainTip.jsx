import { useId } from 'react'
import './ExplainTip.css'

/**
 * Discoverable explanation for badges, pills, and filter controls (PRODUCT.md §1).
 * Hover, focus, and touch via focus-within — not a raw title= tooltip.
 */
export default function ExplainTip({ text, label = 'Explain' }) {
  const id = useId()
  if (!text) return null
  return (
    <span className="explain-tip-wrap">
      <button
        type="button"
        className="explain-tip-btn mono"
        aria-label={label}
        aria-describedby={id}
      >
        ?
      </button>
      <span role="tooltip" id={id} className="explain-tip-bubble">
        {text}
      </span>
    </span>
  )
}
