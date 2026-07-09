import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  investigationPivotBadge,
  techniqueBadgeLabel,
  techniqueSummaryParts,
  techniquePdfSectionTitle,
  TECHNIQUE_TAXONOMY,
} from './investigationLabels.js'

describe('investigationLabels', () => {
  const atlasItem = {
    type: 'technique',
    source: 'atlas',
    description: 'MITRE ATLAS technique',
    meta: { taxonomy: TECHNIQUE_TAXONOMY.ATLAS },
    id: 'AML.T0000',
  }

  const attackItem = {
    type: 'technique',
    source: 'drawer',
    description: 'MITRE ATT&CK technique mapping',
    meta: { taxonomy: TECHNIQUE_TAXONOMY.ATTACK },
    id: 'T1059',
  }

  const genericItem = {
    type: 'technique',
    source: 'drawer',
    description: 'Technique reference',
    id: 'T0000',
  }

  it('labels ATLAS techniques from taxonomy metadata', () => {
    assert.equal(techniqueBadgeLabel(atlasItem), 'ATLAS')
    assert.equal(investigationPivotBadge(atlasItem), 'ATLAS')
  })

  it('labels ATT&CK techniques from taxonomy metadata', () => {
    assert.equal(techniqueBadgeLabel(attackItem), 'ATT&CK')
    assert.equal(investigationPivotBadge(attackItem), 'ATT&CK')
  })

  it('labels generic techniques without taxonomy claim', () => {
    assert.equal(techniqueBadgeLabel(genericItem), 'TECHNIQUE')
    assert.equal(investigationPivotBadge(genericItem), 'TECHNIQUE')
  })

  it('builds thread summary parts without AI wording', () => {
    const parts = techniqueSummaryParts([atlasItem, attackItem, genericItem])
    assert.deepEqual(parts, ['1 ATLAS technique', '1 ATT&CK technique', '1 technique'])
  })

  it('selects PDF section title from technique taxonomy', () => {
    assert.equal(techniquePdfSectionTitle([atlasItem]), 'ATLAS TECHNIQUE CONTEXT')
    assert.equal(
      techniquePdfSectionTitle([atlasItem, attackItem]),
      'TECHNIQUE CONTEXT',
    )
  })
})
