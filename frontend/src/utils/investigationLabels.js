/** Investigation thread display labels derived from item source/taxonomy. */

export const INV_TYPE_TECHNIQUE = 'technique'

export const TECHNIQUE_TAXONOMY = {
  ATLAS: 'atlas',
  ATTACK: 'attack',
}

/**
 * Resolve technique taxonomy from item metadata — never infer ATLAS from type alone.
 * @param {{ source?: string, description?: string, meta?: { taxonomy?: string } } | null | undefined} item
 */
export function techniqueTaxonomyFromItem(item) {
  if (!item) return null
  const metaTax = (item.meta?.taxonomy || '').toLowerCase()
  if (metaTax === TECHNIQUE_TAXONOMY.ATTACK) return TECHNIQUE_TAXONOMY.ATTACK
  if (metaTax === TECHNIQUE_TAXONOMY.ATLAS) return TECHNIQUE_TAXONOMY.ATLAS

  const source = (item.source || '').toLowerCase()
  if (source === 'atlas') return TECHNIQUE_TAXONOMY.ATLAS

  const desc = (item.description || '').toLowerCase()
  if (desc.includes('mitre attack') || desc.includes('att&ck')) {
    return TECHNIQUE_TAXONOMY.ATTACK
  }
  if (desc.includes('atlas')) return TECHNIQUE_TAXONOMY.ATLAS

  return null
}

/**
 * @param {{ source?: string, description?: string, meta?: { taxonomy?: string } } | null | undefined} item
 */
export function techniqueBadgeLabel(item) {
  const tax = techniqueTaxonomyFromItem(item)
  if (tax === TECHNIQUE_TAXONOMY.ATLAS) return 'ATLAS'
  if (tax === TECHNIQUE_TAXONOMY.ATTACK) return 'ATT&CK'
  return 'TECHNIQUE'
}

/**
 * @param {number} count
 * @param {'atlas'|'attack'|null} [taxonomy]
 */
export function techniqueSummaryPhrase(count, taxonomy = null) {
  const noun = count === 1 ? 'technique' : 'techniques'
  if (taxonomy === TECHNIQUE_TAXONOMY.ATLAS) return `${count} ATLAS ${noun}`
  if (taxonomy === TECHNIQUE_TAXONOMY.ATTACK) return `${count} ATT&CK ${noun}`
  return `${count} ${noun}`
}

/**
 * @param {Array<{ type?: string, source?: string, description?: string, meta?: object }>} items
 */
export function techniqueSummaryParts(items) {
  const techniques = (items || []).filter(i => i.type === INV_TYPE_TECHNIQUE)
  if (!techniques.length) return []

  let atlas = 0
  let attack = 0
  let generic = 0
  for (const item of techniques) {
    const tax = techniqueTaxonomyFromItem(item)
    if (tax === TECHNIQUE_TAXONOMY.ATLAS) atlas += 1
    else if (tax === TECHNIQUE_TAXONOMY.ATTACK) attack += 1
    else generic += 1
  }

  const parts = []
  if (atlas) parts.push(techniqueSummaryPhrase(atlas, TECHNIQUE_TAXONOMY.ATLAS))
  if (attack) parts.push(techniqueSummaryPhrase(attack, TECHNIQUE_TAXONOMY.ATTACK))
  if (generic) parts.push(techniqueSummaryPhrase(generic, null))
  return parts
}

/**
 * @param {{ type?: string, source?: string, description?: string, meta?: object } | null | undefined} item
 */
export function investigationPivotBadge(item) {
  if (!item) return null
  switch (item.type) {
    case 'cve': return 'CVE'
    case 'ioc': return 'IOC'
    case 'actor': return 'ACTOR'
    case INV_TYPE_TECHNIQUE: return techniqueBadgeLabel(item)
    default: return '—'
  }
}

/**
 * PDF section title for technique items grouped by taxonomy.
 * @param {Array<{ type?: string, source?: string, description?: string, meta?: object }>} items
 */
export function techniquePdfSectionTitle(items) {
  const parts = techniqueSummaryParts(items)
  if (!parts.length) return 'TECHNIQUE CONTEXT'
  if (parts.length === 1 && parts[0].includes('ATLAS')) return 'ATLAS TECHNIQUE CONTEXT'
  if (parts.length === 1 && parts[0].includes('ATT&CK')) return 'ATT&CK TECHNIQUE CONTEXT'
  return 'TECHNIQUE CONTEXT'
}
