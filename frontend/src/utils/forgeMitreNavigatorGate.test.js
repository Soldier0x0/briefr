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

  it('top nav, coverage-scoped hunt pack, toggle deselect, no status chrome', () => {
    const forge = read(FORGE)
    assert.match(forge, /label:\s*'ATT&CK navigator'/)
    assert.match(forge, /showHuntPack/)
    assert.match(forge, /viewMode === 'coverage'/)
    assert.match(forge, /clearTechniqueSelection/)
    assert.match(forge, /techniqueId === selectedTechnique/)
    assert.doesNotMatch(forge, /StatusChip/)
    assert.doesNotMatch(forge, /ForgeStatusLegend/)
    assert.doesNotMatch(forge, /fg-counts-nav/)
    const css = read(CSS)
    assert.match(css, /\.fg-navigator-scroll/)
    assert.match(css, /\.fg-tactic-col-wrap/)
    assert.match(css, /flex-direction:\s*column/)
    assert.match(css, /\.fg-nav-tabs \{[\s\S]*flex-direction:\s*row/)
    assert.doesNotMatch(css, /grid-template-columns:\s*var\(--fg-nav-w\)/)
    assert.doesNotMatch(css, /\.fg-tactic-col--expanded/)
    assert.doesNotMatch(css, /\.fg-tactic-expand\b/)
  })

  it('avoids forcing huge empty tactic columns', () => {
    const css = read(CSS)
    assert.doesNotMatch(css, /\.fg-tactic-col-wrap\s*\{[^}]*min-height:\s*min\(70vh,\s*640px\)/)
    assert.doesNotMatch(css, /\.fg-tactic-col\s*\{[^}]*min-height:\s*min\(70vh,\s*640px\)/)
  })

  it('shows EmptyState when coverage has no techniques', () => {
    const view = read(COVERAGE)
    assert.match(view, /EmptyState/)
    assert.doesNotMatch(view, /fg-panel-empty/)
  })

  it('Forge.css brace-balanced (guards lightningcss @keyframes minify crash)', () => {
    const css = read(CSS)
    const cleanCss = css
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/'[^']*'/g, '')
      .replace(/"[^"]*"/g, '')
    let bal = 0
    for (const ch of cleanCss) {
      if (ch === '{') bal += 1
      else if (ch === '}') bal -= 1
      assert.ok(bal >= 0, 'extra closing brace')
    }
    assert.equal(bal, 0)
    assert.match(
      css,
      /\.fg-tech-node-active \.fg-tech-node-id \{\s*color: var\(--accent-selected\);\s*\}/,
    )
  })
})
