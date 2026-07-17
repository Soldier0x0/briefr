import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { forgeCoverageHref } from '../components/DetailDrawer/helpers.js'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), 'utf8')
}

describe('PM-4e drawer ↔ Forge MITRE cross-links', () => {
  it('builds Forge coverage deep links', () => {
    assert.equal(forgeCoverageHref('T1190'), '/?tab=forge&view=coverage&technique=T1190')
    assert.equal(forgeCoverageHref('T1059.001'), '/?tab=forge&view=coverage&technique=T1059.001')
    assert.equal(forgeCoverageHref(''), null)
  })

  it('wires Open in Forge from Intel tab and openForgeTechnique nav', () => {
    const intel = read('components/DetailDrawer/IntelTab.jsx')
    assert.match(intel, /Open in Forge/)
    assert.match(intel, /onOpenForgeTechnique/)
    assert.match(intel, /forgeCoverageHref/)

    const app = read('App.jsx')
    assert.match(app, /openForgeTechnique/)
    assert.match(app, /view',\s*'coverage'/)

    const ctx = read('context/InvestigationContext.jsx')
    assert.match(ctx, /openForgeTechnique/)
    assert.match(ctx, /TECHNIQUE_TAXONOMY\.ATTACK/)

    const forge = read('components/Forge.jsx')
    assert.match(forge, /setRailOpen\(true\)/)
    assert.match(forge, /writeUrl\(\{ view: 'coverage', technique: techniqueId/)

    const rail = read('components/forge/HuntPackRail.jsx')
    assert.match(rail, /onOpenCve/)
    assert.match(rail, /openCveById/)
  })
})
