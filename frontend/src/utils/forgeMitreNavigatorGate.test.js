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

  it('shows technique id + name only — no K/GAP chips or column +', () => {
    const view = read(COVERAGE)
    assert.match(view, /fg-tech-node-name/)
    assert.doesNotMatch(view, /fg-tactic-expand/)
    assert.doesNotMatch(view, /StatusChip/)
    assert.doesNotMatch(view, /fg-tech-node-kev/)
    assert.doesNotMatch(view, /fg-tech-node--gap/)
    assert.match(view, /fg-tech-tree-toggle--spacer/)
  })

  it('hunt pack docks below workspace; navigator uses full width', () => {
    const forge = read(FORGE)
    assert.match(forge, /label:\s*'ATT&CK navigator'/)
    assert.match(forge, /fg-shell--detail-open/)
    assert.match(forge, /hidden=\{!railOpen\}/)
    const css = read(CSS)
    assert.match(css, /\.fg-navigator-scroll/)
    assert.match(css, /\.fg-tactic-col-wrap/)
    assert.match(css, /grid-template-columns:\s*var\(--fg-nav-w\)/)
    assert.match(css, /\.fg-detail\[hidden\]/)
    assert.doesNotMatch(css, /\.fg-tactic-col--expanded/)
    assert.doesNotMatch(css, /\.fg-tactic-expand\b/)
  })

  it('Forge.css brace-balanced (guards lightningcss @keyframes minify crash)', () => {
    const css = read(CSS)
    let bal = 0
    for (const ch of css) {
      if (ch === '{') bal += 1
      else if (ch === '}') bal -= 1
      assert.ok(bal >= 0, 'extra closing brace')
    }
    assert.equal(bal, 0)
    // Regression: #652 merge dropped `}` before `.fg-tech-node-name`
    assert.match(
      css,
      /\.fg-tech-node-active \.fg-tech-node-id \{\s*color: var\(--accent-selected\);\s*\}/,
    )
  })
})
