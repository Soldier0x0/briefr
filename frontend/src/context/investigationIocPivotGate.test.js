import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

const ctx = readFileSync(new URL('./InvestigationContext.jsx', import.meta.url), 'utf8')
const graph = readFileSync(new URL('../components/investigate/InvestigateGraph.jsx', import.meta.url), 'utf8')
const app = readFileSync(new URL('../App.jsx', import.meta.url), 'utf8')

function extractAppLayoutInvestigateGraphBlock(source) {
  const layoutStart = source.indexOf('function AppLayout(')
  assert.ok(layoutStart >= 0, 'AppLayout not found')
  const graphIdx = source.indexOf('<InvestigateGraph', layoutStart)
  assert.ok(graphIdx >= 0, 'AppLayout InvestigateGraph not found')
  const closeIdx = source.indexOf('/>', graphIdx)
  assert.ok(closeIdx >= 0, 'InvestigateGraph JSX not closed')
  return source.slice(graphIdx, closeIdx)
}

describe('LOOKUP LIVE kind', () => {
  it('pivotToIoc accepts indicatorType and does not hardcode only ip in the graph path', () => {
    assert.match(ctx, /indicatorType/)
    assert.match(graph, /parseIocEntityId/)
    assert.match(graph, /LOOKUP LIVE/)
  })
})

describe('AppLayout InvestigateGraph wiring', () => {
  it('forwards pivot props by name from AppLayout scope', () => {
    const block = extractAppLayoutInvestigateGraphBlock(app)
    assert.match(block, /onWatchlistChange=\{onWatchlistChange\}/)
    assert.match(block, /onOpenForgeCampaigns=\{onOpenForgeCampaigns\}/)
    assert.match(block, /onOpenAdvisories=\{onOpenAdvisories\}/)
    assert.doesNotMatch(block, /handleWatchlistChange/)
    assert.doesNotMatch(block, /\bonOpenAdvisories=\{openAdvisories\}/)
    assert.doesNotMatch(block, /\bonOpenForgeCampaigns=\{openForgeCampaigns\}/)
  })
})
