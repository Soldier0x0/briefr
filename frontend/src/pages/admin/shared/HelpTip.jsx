import { useId } from 'react'
import { Info } from 'lucide-react'

export default function HelpTip({ text }) {
  const id = useId()
  if (!text) return null
  return (
    <span className="help-tip-wrap">
      <button type="button" className="info-tip" aria-describedby={id}>
        <Info size={13} strokeWidth={2} />
      </button>
      <span role="tooltip" id={id} className="help-tip-bubble">{text}</span>
    </span>
  )
}
