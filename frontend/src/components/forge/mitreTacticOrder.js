/**
 * Enterprise ATT&CK tactic display order (kill-chain left→right).
 * Coverage rows use title-cased STIX phase names from feeds/mitre.py.
 * Unknown tactics append after this list.
 */
export const MITRE_TACTIC_ORDER = Object.freeze([
  'Reconnaissance',
  'Resource Development',
  'Initial Access',
  'Execution',
  'Persistence',
  'Privilege Escalation',
  'Defense Evasion',
  'Credential Access',
  'Discovery',
  'Lateral Movement',
  'Collection',
  'Command and Control',
  'Exfiltration',
  'Impact',
])

/** Parent technique id — `T1059.001` → `T1059`; top-level stays itself. */
export function parentTechniqueId(techniqueId) {
  const id = String(techniqueId || '')
  const dot = id.indexOf('.')
  return dot === -1 ? id : id.slice(0, dot)
}

/**
 * Group coverage techniques into ordered tactic columns.
 * Within each tactic, nest sub-techniques under their parent when both appear.
 */
export function groupCoverageByTactic(techniques = []) {
  const byTactic = new Map()
  for (const technique of techniques) {
    const tactic = technique.tactic || 'Uncategorized'
    if (!byTactic.has(tactic)) byTactic.set(tactic, [])
    byTactic.get(tactic).push(technique)
  }

  const known = MITRE_TACTIC_ORDER.filter((t) => byTactic.has(t))
  const extras = [...byTactic.keys()]
    .filter((t) => !MITRE_TACTIC_ORDER.includes(t))
    .sort((a, b) => a.localeCompare(b))

  return [...known, ...extras].map((tactic) => ({
    tactic,
    techniques: byTactic.get(tactic) || [],
    trees: buildTechniqueTrees(byTactic.get(tactic) || []),
  }))
}

function buildTechniqueTrees(techniques) {
  const byId = new Map(techniques.map((t) => [t.technique_id, t]))
  const children = new Map()
  const roots = []

  for (const technique of techniques) {
    const id = technique.technique_id
    const parentId = parentTechniqueId(id)
    if (parentId !== id && byId.has(parentId)) {
      if (!children.has(parentId)) children.set(parentId, [])
      children.get(parentId).push(technique)
    } else {
      roots.push(technique)
    }
  }

  return roots.map((technique) => ({
    technique,
    children: children.get(technique.technique_id) || [],
  }))
}
