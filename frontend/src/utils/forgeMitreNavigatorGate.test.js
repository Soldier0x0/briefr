import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const COVERAGE = path.join(ROOT, 'components', 'forge', 'CoverageView.jsx')
const FORGE = path.join(ROOT, 'components', 'Forge.jsx')
const CSS = path.join(ROOT, 'components', 'Forge.css')

function read(file) {
  return fs.readFileSync(file, 'utf8')
}

describe('PM-4d Forge MITRE navigator gate', () => {
  it('renders tactic-column navigator, not flat-only tech rows', () => {
    const view = read(COVERAGE)
    assert.match(view, /fg-navigator/)
    assert.match(view, /groupCoverageByTactic/)
    assert.match(view, /MITRE ATT&amp;CK NAVIGATOR/)
    assert.match(view, /fg-tactic-col/)
    assert.match(view, /fg-tech-node/)
    assert.doesNotMatch(view, /fg-tech-row/)
  })

  it('shows technique names directly — no per-column + expand gate', () => {
    const view = read(COVERAGE)
    assert.match(view, /fg-tech-node-name/)
    assert.doesNotMatch(view, /fg-tactic-expand/)
    assert.doesNotMatch(view, /Collapse column detail/)
    assert.match(view, /fg-tech-tree-toggle--spacer/)
  })

  it('nav label is ATT&CK navigator; CSS has uniform column width', () => {
    assert.match(read(FORGE), /label:\s*'ATT&CK navigator'/)
    const css = read(CSS)
    assert.match(css, /\.fg-navigator-scroll/)
    assert.match(css, /\.fg-tactic-col-wrap/)
    assert.match(css, /\.fg-tactic-col/)
    assert.match(css, /\.fg-tech-node/)
    assert.doesNotMatch(css, /\.fg-tactic-col--expanded/)
    assert.doesNotMatch(css, /\.fg-tactic-expand\b/)
  })
})
