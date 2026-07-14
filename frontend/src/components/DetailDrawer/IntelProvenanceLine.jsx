import ControlTooltip from '../ControlTooltip.jsx'
import {
  formatIntelProvenanceLine,
  intelProvenanceTooltip,
} from '../../utils/intelProvenance.js'

export default function IntelProvenanceLine({ provenance, className = '' }) {
  const line = formatIntelProvenanceLine(provenance)
  const tip = intelProvenanceTooltip(provenance)
  if (!line) return null

  return (
    <ControlTooltip text={tip} trigger="hover-focus">
      <p className={`drawer-intel-provenance mono${className ? ` ${className}` : ''}`}>
        {line}
      </p>
    </ControlTooltip>
  )
}
