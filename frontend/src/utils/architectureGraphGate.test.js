import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const CSS_PATH = path.join(ROOT, 'pages', 'security-architecture', 'SecurityArchitecturePage.css')
const GRAPH_SECTION = path.join(ROOT, 'pages', 'security-architecture', 'sections', 'ArchitectureGraphSection.jsx')
const SA_PAGE = path.join(ROOT, 'pages', 'security-architecture', 'SecurityArchitecturePage.jsx')
const OVERVIEW_PAGE = path.join(ROOT, 'pages', 'admin', 'OverviewPage.jsx')

function read(file) {
  return fs.readFileSync(file, 'utf8')
}

function blockForSelector(css, selector) {
  const re = new RegExp(`${selector.replace('.', '\\.')}\\s*\\{([^}]+)\\}`)
  return re.exec(css)?.[1] || ''
}

describe('PM-3 architecture graph gate', () => {
  it('PM-3a: graph canvas uses compact height and blocks text selection', () => {
    const css = read(CSS_PATH)
    const canvas = blockForSelector(css, '.sa-graph-canvas')
    assert.match(canvas, /height:\s*min\(70vh/, 'graph canvas should lock to ~70vh, not a page-length scroll')
    assert.match(canvas, /max-height:\s*70vh/, 'graph canvas should cap height at 70vh')
    assert.match(canvas, /user-select:\s*none/, 'graph canvas should disable text selection while panning')
    const graphSection = read(GRAPH_SECTION)
    assert.match(graphSection, /zoomAtCursor/, 'wheel zoom should anchor at cursor')
    assert.match(graphSection, /truncateNodeLabel/, 'node labels should truncate inside the rect')
    assert.doesNotMatch(graphSection, /viewBox=\{`0 0 \$\{viewWidth\}/, 'fit uses CSS pixels without content viewBox')
  })

  it('PM-3a-focus: non-neighbors dim strongly when a node is focused', () => {
    const css = read(CSS_PATH)
    const dim = blockForSelector(css, '.sa-graph-node-dim')
    assert.match(dim, /opacity:\s*0\.1/, 'focused selection should dim non-neighbors strongly')
    const graphSection = read(GRAPH_SECTION)
    assert.match(graphSection, /sa-graph-node-dim/, 'nodes use dim class for non-neighbors')
  })

  it('PM-3b: graph toolbar exposes fit-to-view control', () => {
    const graphSection = read(GRAPH_SECTION)
    assert.match(graphSection, /FIT GRAPH/i, 'fit graph button should exist')
    assert.match(graphSection, /computeFitView/, 'initial view should use fit-to-view helper')
  })

  it('PM-3c: system architecture section inlines node detail and hides empty rail', () => {
    const saPage = read(SA_PAGE)
    const graphSection = read(GRAPH_SECTION)
    assert.match(saPage, /system_architecture.*sa-shell--graph/, 'graph section should use full-width shell without empty rail')
    assert.match(graphSection, /ContextRail/, 'graph section should render inline node detail panel')
    assert.match(graphSection, /selectedNodeId/, 'graph section should accept selected node id')
  })

  it('PM-3d: admin overview exposes corpus drift diagnostic', () => {
    const overview = read(OVERVIEW_PAGE)
    assert.match(overview, /corpus-drift|corpusDrift/i, 'admin overview should expose corpus drift check')
  })
})
