import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { humanizeSectionId } from '../pages/security-architecture/constants.js'

describe('PM-2c section labels', () => {
  it('humanizeSectionId maps mitre_attack to MITRE ATT&CK', () => {
    assert.equal(humanizeSectionId('mitre_attack'), 'MITRE ATT&CK')
  })

  it('humanizeSectionId still title-cases generic section ids', () => {
    assert.equal(humanizeSectionId('trust_boundaries'), 'Trust Boundaries')
    assert.equal(humanizeSectionId('attack_surface'), 'Attack Surface')
  })
})
