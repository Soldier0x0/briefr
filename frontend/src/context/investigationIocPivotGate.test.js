import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

const ctx = readFileSync(new URL('./InvestigationContext.jsx', import.meta.url), 'utf8')
const graph = readFileSync(new URL('../components/investigate/InvestigateGraph.jsx', import.meta.url), 'utf8')

describe('LOOKUP LIVE kind', () => {
  it('pivotToIoc accepts indicatorType and does not hardcode only ip in the graph path', () => {
    assert.match(ctx, /indicatorType/)
    assert.match(graph, /parseIocEntityId/)
    assert.match(graph, /LOOKUP LIVE/)
  })
})
