import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))

describe('admin labeled control rows', () => {
  it('defines the shared field / baseline-align CSS contract', () => {
    const css = readFileSync(join(here, '../AdminPage.css'), 'utf8')
    assert.match(css, /\.admin-field\b/)
    assert.match(css, /\.admin-field-label\b/)
    assert.match(css, /\.admin-filter-bar--fields\b/)
    assert.match(css, /align-items:\s*flex-end/)
    assert.match(css, /min-height:\s*var\(--control-height-md\)/)
  })

  it('uses stacked fields on Table browser (not inline label+marginLeft)', () => {
    const src = readFileSync(join(here, 'DbExplorerPanel.jsx'), 'utf8')
    assert.match(src, /admin-filter-bar--fields/)
    assert.match(src, /admin-field-label/)
    assert.doesNotMatch(src, /marginLeft:\s*'0\.35rem'/)
  })

  it('uses stacked fields on AI ops + webhook labeled toolbars', () => {
    const ai = readFileSync(join(here, 'AiOperationsPage.jsx'), 'utf8')
    const wh = readFileSync(join(here, 'WebhooksPage.jsx'), 'utf8')
    assert.match(ai, /admin-filter-bar--fields/)
    assert.match(wh, /admin-filter-bar--fields/)
    assert.match(wh, /admin-toolbar--fields/)
    assert.doesNotMatch(ai, /marginLeft:\s*'0\.35rem'/)
    assert.doesNotMatch(wh, /marginLeft:\s*'0\.35rem'/)
  })
})
