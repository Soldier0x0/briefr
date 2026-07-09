import {
  formatIntelProvenanceLine,
  intelProvenanceTooltip,
} from '../../utils/intelProvenance.js'

export default function IntelProvenanceLine({ provenance, className = '' }) {
  const line = formatIntelProvenanceLine(provenance)
  if (!line) return null

  return (
    <p
      className={`drawer-intel-provenance mono${className ? ` ${className}` : ''}`}
      title={intelProvenanceTooltip(provenance)}
    >
      {line}
    </p>
  )
}
