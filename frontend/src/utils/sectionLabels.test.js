import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { humanizeSectionId } from '../pages/security-architecture/constants.js'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

describe('PM-2c section labels', () => {
  it('humanizeSectionId maps mitre_attack to MITRE ATT&CK', () => {
    assert.equal(humanizeSectionId('mitre_attack'), 'MITRE ATT&CK')
  })

  it('humanizeSectionId still title-cases generic section ids', () => {
    assert.equal(humanizeSectionId('trust_boundaries'), 'Trust Boundaries')
    assert.equal(humanizeSectionId('attack_surface'), 'Attack Surface')
  })

  it('MitreSection uses one shared layout toolbar for tactic grids', () => {
    const src = fs.readFileSync(
      path.join(ROOT, 'pages/security-architecture/sections/MitreSection.jsx'),
      'utf8',
    )
    assert.match(src, /layoutGroupId=["']sa-mitre["']/)
    assert.match(src, /showLayoutToggles=\{false\}/)
    assert.match(src, /data-grid-layout-toolbar/)
  })
})
