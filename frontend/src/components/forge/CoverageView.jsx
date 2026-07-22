import { useMemo, useState } from 'react'
import { EmptyState } from '../ui/index.js'
import { SkeletonRows } from './shared.jsx'
import { groupCoverageByTactic } from './mitreTacticOrder.js'

function TechniqueNode({ technique, active, onSelect }) {
  const title = [
    technique.technique_id,
    technique.name,
    technique.cve_count != null
      ? `${technique.cve_count} CVE${technique.cve_count === 1 ? '' : 's'}`
      : null,
  ].filter(Boolean).join(' · ')

  return (
    <button
      type="button"
      className={['fg-tech-node', active ? 'fg-tech-node-active' : ''].filter(Boolean).join(' ')}
      onClick={() => onSelect(technique.technique_id)}
      aria-pressed={active}
      title={title}
    >
      <span className="fg-tech-node-id mono">{technique.technique_id}</span>
      <span className="fg-tech-node-name">{technique.name || technique.technique_id}</span>
    </button>
  )
}

function TacticColumn({ tactic, techniques, trees, selectedTechnique, onSelectTechnique }) {
  // Expand stays open until the user collapses via ▾ — selecting a technique
  // must not reset this state (official ATT&CK-style persistence).
  const [openParents, setOpenParents] = useState(() => {
    const initial = new Set()
    for (const { technique, children } of trees) {
      if (children.length > 0) initial.add(technique.technique_id)
    }
    return initial
  })

  function setParentOpen(id, open) {
    setOpenParents((prev) => {
      const next = new Set(prev)
      if (open) next.add(id)
      else next.delete(id)
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
                    onClick={(e) => {
                      e.stopPropagation()
                      setParentOpen(technique.technique_id, !parentOpen)
                    }}
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
 * MITRE ATT&CK navigator — tactic columns, technique id + name (matrix-style).
 * Click a technique to open related CVEs / hunt pack below the matrix.
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
          Tactic columns · click a technique for related CVEs and hunt packs
        </p>
      </div>
      {loading ? (
        <SkeletonRows count={10} />
      ) : columns.length === 0 ? (
        <EmptyState
          title={
            stackOnly
              ? 'No techniques linked to CVEs matching your stack'
              : 'No techniques mapped yet — wait for the MITRE feed to populate'
          }
        />
      ) : (
        <div
          className="fg-navigator-scroll fg-navigator-scroll--populated"
          role="list"
          aria-label="ATT&CK tactics"
        >
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
