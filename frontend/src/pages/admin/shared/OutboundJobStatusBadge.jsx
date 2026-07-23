import ControlTooltip from '../../../components/ControlTooltip.jsx'
import {
  outboundStatusBadgeClass,
  outboundStatusHint,
  outboundStatusLabel,
} from '../outboundJobStatus.js'

export default function OutboundJobStatusBadge({ status, mode = 'operator' }) {
  const label = outboundStatusLabel(status, mode)
  const hint = outboundStatusHint(status)
  const badgeClass = outboundStatusBadgeClass(status)

  return (
    <ControlTooltip text={hint || label} trigger="hover-focus">
      <span className={`badge ${badgeClass}`}>{label}</span>
    </ControlTooltip>
  )
}
