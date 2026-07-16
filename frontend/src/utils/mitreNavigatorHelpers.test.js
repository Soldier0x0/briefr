import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  MITRE_TACTIC_ORDER,
  parentTechniqueId,
  groupCoverageByTactic,
} from '../components/forge/mitreTacticOrder.js'

describe('mitreTacticOrder helpers (PM-4d)', () => {
  it('orders known tactics left-to-right and nests sub-techniques', () => {
    assert.ok(MITRE_TACTIC_ORDER.indexOf('Initial Access') < MITRE_TACTIC_ORDER.indexOf('Impact'))
    assert.equal(parentTechniqueId('T1059.001'), 'T1059')
    assert.equal(parentTechniqueId('T1190'), 'T1190')

    const columns = groupCoverageByTactic([
      { technique_id: 'T1059.001', name: 'PowerShell', tactic: 'Execution', status: 'gap' },
      { technique_id: 'T1059', name: 'Command and Scripting Interpreter', tactic: 'Execution', status: 'community' },
      { technique_id: 'T1190', name: 'Exploit Public-Facing Application', tactic: 'Initial Access', status: 'yours' },
      { technique_id: 'T9999', name: 'Custom', tactic: 'Weird Tactic', status: 'gap' },
    ])

    assert.equal(columns[0].tactic, 'Initial Access')
    assert.equal(columns[1].tactic, 'Execution')
    assert.equal(columns[2].tactic, 'Weird Tactic')
    assert.equal(columns[1].trees.length, 1)
    assert.equal(columns[1].trees[0].technique.technique_id, 'T1059')
    assert.equal(columns[1].trees[0].children[0].technique_id, 'T1059.001')
  })
})
