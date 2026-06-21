import { useId } from 'react'

export default function HelpTip({ text }) {
  const id = useId()
  if (!text) return null
  return (
    <span className="help-tip-wrap">
      <button type="button" className="info-tip" aria-describedby={id}>ⓘ</button>
      <span role="tooltip" id={id} className="help-tip-bubble">{text}</span>
    </span>
  )
}
