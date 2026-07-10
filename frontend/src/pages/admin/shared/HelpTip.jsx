import { Info } from 'lucide-react'
import Tooltip from '../../../components/ui/Tooltip.jsx'

export default function HelpTip({ text }) {
  if (!text) return null
  return (
    <Tooltip
      text={text}
      asChild
      trigger="hover-focus"
      className="help-tip-wrap"
      bubbleClassName="help-tip-bubble"
      maxWidth={280}
    >
      <button type="button" className="info-tip">
        <Info size={13} strokeWidth={2} />
      </button>
    </Tooltip>
  )
}
