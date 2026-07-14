import { useMemo } from 'react'
import Tooltip from '../ui/Tooltip.jsx'
import { SkeletonRows, StatusChip } from './shared.jsx'

function CoverageRow({ technique, active, onSelect }) {
  const caseStudyCount = technique.case_study_count || 0
  return (
    <li>
      <button
        type="button"
        className={`fg-tech-row${active ? ' fg-tech-row-active' : ''}`}
        onClick={() => onSelect(technique.technique_id)}
        aria-pressed={active}
      >
        <span className="fg-tech-id mono">{technique.technique_id}</span>
        <span className="fg-tech-name">{technique.name || technique.technique_id}</span>
        <span className="fg-tech-counts mono">
          {technique.cve_count} CVE{technique.cve_count === 1 ? '' : 's'}
          {technique.kev_count > 0 && (
            <span
              className="fg-kev-count"
              title="CVEs on CISA's Known Exploited Vulnerabilities catalog — confirmed active exploitation"
            > · {technique.kev_count} KEV</span>
          )}
        </span>
        {caseStudyCount > 0 && (
          <Tooltip text="Real-world MITRE ATLAS incidents linked to CVEs mapped to this technique — open the hunt pack rail to read them.">
            <span className="fg-case-study-chip mono">
              Case studies ({caseStudyCount})
            </span>
          </Tooltip>
        )}
        <StatusChip status={technique.status} />
      </button>
    </li>
  )
}

export default function CoverageView({ coverage, loading, stackOnly, selectedTechnique, onSelectTechnique }) {
  const byTactic = useMemo(() => {
    const groups = new Map()
    for (const technique of coverage?.techniques || []) {
      const tactic = technique.tactic || 'Uncategorized'
      if (!groups.has(tactic)) groups.set(tactic, [])
      groups.get(tactic).push(technique)
    }
    return Array.from(groups.entries())
  }, [coverage])

  return (
    <section className="fg-map" aria-label="MITRE coverage map">
      <h2 className="fg-section-label mono">COVERAGE MAP</h2>
      {loading ? (
        <SkeletonRows count={10} />
      ) : byTactic.length === 0 ? (
        <p className="fg-panel-empty mono">
          {stackOnly
            ? '// No techniques linked to CVEs matching your stack'
            : '// No techniques mapped yet — wait for the MITRE feed to populate'}
        </p>
      ) : (
        byTactic.map(([tactic, techniques]) => (
          <div key={tactic} className="fg-tactic-group">
            <h3 className="fg-tactic-label mono">{tactic.toUpperCase()}</h3>
            <ul className="fg-tech-list">
              {techniques.map(technique => (
                <CoverageRow
                  key={technique.technique_id}
                  technique={technique}
                  active={selectedTechnique === technique.technique_id}
                  onSelect={onSelectTechnique}
                />
              ))}
            </ul>
          </div>
        ))
      )}
    </section>
  )
}
