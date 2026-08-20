import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

const src = readFileSync(new URL('./InvestigateGraph.jsx', import.meta.url), 'utf8')

describe('InvestigateGraph canvas gates', () => {
  it('does not expand on single click', () => {
    assert.doesNotMatch(src, /onClick=\{\(\) => expandNode\(node\)\}/)
    assert.match(src, /onDoubleClick/)
  })
  it('uses a non-passive wheel listener', () => {
    assert.match(src, /addEventListener\('wheel', handler, \{ passive: false \}\)/)
    assert.doesNotMatch(src, /onWheel=/)
  })
})
