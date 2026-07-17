import { useMemo, useState } from 'react'
import Tooltip from '../ui/Tooltip.jsx'
import { SkeletonRows, StatusChip } from './shared.jsx'
import { groupCoverageByTactic } from './mitreTacticOrder.js'

function TechniqueNode({ technique, active, onSelect }) {
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
      ].filter(Boolean).join(' ')}
      onClick={() => onSelect(technique.technique_id)}
      aria-pressed={active}
      title={title}
    >
      <span className="fg-tech-node-id mono">{technique.technique_id}</span>
      <span className="fg-tech-node-name">{technique.name || technique.technique_id}</span>
      <span className="fg-tech-node-meta mono" aria-hidden="true">
        {technique.kev_count > 0 && <span className="fg-tech-node-kev" title="KEV">K</span>}
        {caseStudyCount > 0 && <span className="fg-tech-node-cs" title="Case studies">C</span>}
        <StatusChip status={technique.status} />
      </span>
    </button>
  )
}

function TacticColumn({ tactic, techniques, trees, selectedTechnique, onSelectTechnique }) {
  // Parents with children start open so sub-techniques are visible without an extra click.
  const [openParents, setOpenParents] = useState(() => {
    const initial = new Set()
    for (const { technique, children } of trees) {
      if (children.length > 0) initial.add(technique.technique_id)
    }
    return initial
  })

  function toggleParent(id) {
    setOpenParents((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="fg-tactic-col">
      <div className="fg-tactic-col-head">
        <h3 className="fg-tactic-label mono">{tactic.toUpperCase()}</h3>
        <span className="fg-tactic-count mono" title="Techniques in this tactic">
          {techniques.length}
        </span>
      </div>
      <ul className="fg-tech-node-list" aria-label={`${tactic} techniques`}>
        {trees.map(({ technique, children }) => {
          const hasChildren = children.length > 0
          const parentOpen = openParents.has(technique.technique_id)
          return (
            <li key={technique.technique_id} className="fg-tech-tree">
              <div className="fg-tech-tree-row">
                {hasChildren ? (
                  <button
                    type="button"
                    className="fg-tech-tree-toggle mono"
                    aria-expanded={parentOpen}
                    aria-label={`${parentOpen ? 'Collapse' : 'Expand'} ${technique.technique_id} sub-techniques`}
                    onClick={() => toggleParent(technique.technique_id)}
                  >
                    {parentOpen ? '▾' : '▸'}
                  </button>
                ) : (
                  <span className="fg-tech-tree-toggle fg-tech-tree-toggle--spacer" aria-hidden="true" />
                )}
                <TechniqueNode
                  technique={technique}
                  active={selectedTechnique === technique.technique_id}
                  onSelect={onSelectTechnique}
                />
              </div>
              {hasChildren && parentOpen && (
                <ul className="fg-tech-node-list fg-tech-node-list--sub">
                  {children.map((child) => (
                    <li key={child.technique_id}>
                      <div className="fg-tech-tree-row">
                        <span className="fg-tech-tree-toggle fg-tech-tree-toggle--spacer" aria-hidden="true" />
                        <TechniqueNode
                          technique={child}
                          active={selectedTechnique === child.technique_id}
                          onSelect={onSelectTechnique}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/**
 * PM-4d: MITRE ATT&CK navigator — uniform tactic columns with technique
 * id + name always visible. Technique nodes open the hunt-pack rail via
 * onSelectTechnique (?view=coverage&technique=…).
 */
export default function CoverageView({ coverage, loading, stackOnly, selectedTechnique, onSelectTechnique }) {
  const columns = useMemo(
    () => groupCoverageByTactic(coverage?.techniques || []),
    [coverage],
  )

  const hasCaseStudies = useMemo(
    () => (coverage?.techniques || []).some((t) => (t.case_study_count || 0) > 0),
    [coverage],
  )

  return (
    <section className="fg-map fg-navigator" aria-label="MITRE ATT&CK navigator">
      <div className="fg-navigator-head">
        <h2 className="fg-section-label mono">MITRE ATT&amp;CK NAVIGATOR</h2>
        <p className="fg-navigator-hint mono">
          Tactic columns · click a technique for coverage + hunt packs
        </p>
        {hasCaseStudies && (
          <p className="fg-tactic-legend mono">
            <Tooltip text="Real-world MITRE ATLAS incidents linked to CVEs mapped to this technique — open the hunt pack rail to read them.">
              <span>C = case studies</span>
            </Tooltip>
            {' · '}
            <span>K = KEV</span>
          </p>
        )}
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
            <div key={tactic} role="listitem" className="fg-tactic-col-wrap">
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
