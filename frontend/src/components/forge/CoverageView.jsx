import { useMemo, useState } from 'react'
import Tooltip from '../ui/Tooltip.jsx'
import { SkeletonRows, StatusChip } from './shared.jsx'
import { groupCoverageByTactic } from './mitreTacticOrder.js'

function TechniqueNode({ technique, active, dense, onSelect }) {
  const caseStudyCount = technique.case_study_count || 0
  const title = [
    technique.technique_id,
    technique.name,
    `${technique.cve_count} CVE${technique.cve_count === 1 ? '' : 's'}`,
    technique.kev_count > 0 ? `${technique.kev_count} KEV` : null,
    caseStudyCount > 0 ? `${caseStudyCount} case stud${caseStudyCount === 1 ? 'y' : 'ies'}` : null,
  ].filter(Boolean).join(' · ')

  return (
    <button
      type="button"
      className={[
        'fg-tech-node',
        `fg-tech-node--${technique.status || 'gap'}`,
        active ? 'fg-tech-node-active' : '',
        dense ? 'fg-tech-node--dense' : '',
      ].filter(Boolean).join(' ')}
      onClick={() => onSelect(technique.technique_id)}
      aria-pressed={active}
      title={title}
    >
      <span className="fg-tech-node-id mono">{technique.technique_id}</span>
      {dense && (
        <span className="fg-tech-node-name">{technique.name || technique.technique_id}</span>
      )}
      <span className="fg-tech-node-meta mono" aria-hidden="true">
        {technique.kev_count > 0 && <span className="fg-tech-node-kev" title="KEV">K</span>}
        {caseStudyCount > 0 && <span className="fg-tech-node-cs" title="Case studies">C</span>}
        <StatusChip status={technique.status} />
      </span>
    </button>
  )
}

function TacticColumn({ tactic, techniques, trees, selectedTechnique, onSelectTechnique }) {
  const [expanded, setExpanded] = useState(false)
  const [openParents, setOpenParents] = useState(() => new Set())

  function toggleParent(id) {
    setOpenParents((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className={`fg-tactic-col${expanded ? ' fg-tactic-col--expanded' : ''}`}>
      <div className="fg-tactic-col-head">
        <h3 className="fg-tactic-label mono">{tactic.toUpperCase()}</h3>
        <span className="fg-tactic-count mono" title="Techniques in this tactic">
          {techniques.length}
        </span>
        <button
          type="button"
          className="fg-tactic-expand mono"
          aria-expanded={expanded}
          onClick={() => setExpanded((v) => !v)}
          title={expanded ? 'Collapse column detail' : 'Expand column detail'}
        >
          {expanded ? '−' : '+'}
        </button>
      </div>
      <ul className="fg-tech-node-list" aria-label={`${tactic} techniques`}>
        {trees.map(({ technique, children }) => {
          const parentOpen = expanded || openParents.has(technique.technique_id)
          return (
            <li key={technique.technique_id} className="fg-tech-tree">
              <div className="fg-tech-tree-row">
                {children.length > 0 && (
                  <button
                    type="button"
                    className="fg-tech-tree-toggle mono"
                    aria-expanded={parentOpen}
                    aria-label={`${parentOpen ? 'Collapse' : 'Expand'} ${technique.technique_id} sub-techniques`}
                    onClick={() => toggleParent(technique.technique_id)}
                  >
                    {parentOpen ? '▾' : '▸'}
                  </button>
                )}
                <TechniqueNode
                  technique={technique}
                  active={selectedTechnique === technique.technique_id}
                  dense={expanded}
                  onSelect={onSelectTechnique}
                />
              </div>
              {children.length > 0 && parentOpen && (
                <ul className="fg-tech-node-list fg-tech-node-list--sub">
                  {children.map((child) => (
                    <li key={child.technique_id}>
                      <TechniqueNode
                        technique={child}
                        active={selectedTechnique === child.technique_id}
                        dense={expanded}
                        onSelect={onSelectTechnique}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </li>
          )
        })}
      </ul>
      {expanded && techniques.some((t) => (t.case_study_count || 0) > 0) && (
        <p className="fg-tactic-legend mono">
          <Tooltip text="Real-world MITRE ATLAS incidents linked to CVEs mapped to this technique — open the hunt pack rail to read them.">
            <span>C = case studies</span>
          </Tooltip>
          {' · '}
          <span>K = KEV</span>
        </p>
      )}
    </div>
  )
}

/**
 * PM-4d: MITRE ATT&CK navigator — tactic columns + expandable detail /
 * sub-technique trees. Technique nodes open the existing hunt-pack rail
 * via onSelectTechnique (?view=coverage&technique=…).
 */
export default function CoverageView({ coverage, loading, stackOnly, selectedTechnique, onSelectTechnique }) {
  const columns = useMemo(
    () => groupCoverageByTactic(coverage?.techniques || []),
    [coverage],
  )

  return (
    <section className="fg-map fg-navigator" aria-label="MITRE ATT&CK navigator">
      <div className="fg-navigator-head">
        <h2 className="fg-section-label mono">MITRE ATT&amp;CK NAVIGATOR</h2>
        <p className="fg-navigator-hint mono">
          Tactic columns · click a technique for coverage + hunt packs
        </p>
      </div>
      {loading ? (
        <SkeletonRows count={10} />
      ) : columns.length === 0 ? (
        <p className="fg-panel-empty mono">
          {stackOnly
            ? '// No techniques linked to CVEs matching your stack'
            : '// No techniques mapped yet — wait for the MITRE feed to populate'}
        </p>
      ) : (
        <div className="fg-navigator-scroll" role="list" aria-label="ATT&CK tactics">
          {columns.map(({ tactic, techniques, trees }) => (
            <div key={tactic} role="listitem">
              <TacticColumn
                tactic={tactic}
                techniques={techniques}
                trees={trees}
                selectedTechnique={selectedTechnique}
                onSelectTechnique={onSelectTechnique}
              />
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
