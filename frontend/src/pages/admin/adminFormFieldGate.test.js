import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const srcRoot = join(here, '../..')

function read(rel) {
  return readFileSync(join(srcRoot, rel), 'utf8')
}

describe('product-wide labeled control rows', () => {
  it('defines the shared control-field contract in App.css', () => {
    const css = read('App.css')
    assert.match(css, /\.control-field\b/)
    assert.match(css, /\.control-field-label\b/)
    assert.match(css, /\.control-toolbar--fields\b/)
    assert.match(css, /align-items:\s*flex-end/)
    assert.match(css, /min-height:\s*var\(--control-height-md\)/)
  })

  it('keeps admin aliases for filter/toolbar fields', () => {
    const css = read('pages/AdminPage.css')
    assert.match(css, /\.admin-field\b/)
    assert.match(css, /\.admin-filter-bar--fields\b/)
    assert.match(css, /min-height:\s*var\(--control-height-md\)/)
  })

  it('uses stacked fields on Table browser (not inline label+marginLeft)', () => {
    const src = read('pages/admin/DbExplorerPanel.jsx')
    assert.match(src, /admin-filter-bar--fields/)
    assert.match(src, /admin-field-label/)
    assert.doesNotMatch(src, /marginLeft:\s*['"]0\.35rem['"]/)
  })

  it('uses stacked fields on FEED stack, ARCH filters, and Forge pack picker', () => {
    const feed = read('components/FilterBar.jsx')
    const archFw = read('pages/security-architecture/sections/FrameworkSection.jsx')
    const archMitre = read('pages/security-architecture/sections/MitreSection.jsx')
    const archAbuse = read('pages/security-architecture/sections/AbuseCasesSection.jsx')
    const forge = read('components/forge/HuntPackRail.jsx')
    assert.match(feed, /control-toolbar--fields/)
    assert.match(feed, /control-field/)
    assert.match(archFw, /control-toolbar--fields/)
    assert.match(archMitre, /control-toolbar--fields/)
    assert.match(archAbuse, /control-toolbar--fields/)
    assert.match(forge, /control-field/)
  })

  it('uses stacked fields on AI ops + webhook + backups labeled toolbars', () => {
    const ai = read('pages/admin/AiOperationsPage.jsx')
    const wh = read('pages/admin/WebhooksPage.jsx')
    const backups = read('pages/admin/BackupsPage.jsx')
    assert.match(ai, /admin-filter-bar--fields/)
    assert.match(wh, /admin-filter-bar--fields/)
    assert.match(wh, /admin-toolbar--fields/)
    assert.match(backups, /control-field/)
    assert.doesNotMatch(ai, /marginLeft:\s*['"]0\.35rem['"]/)
    assert.doesNotMatch(wh, /marginLeft:\s*['"]0\.35rem['"]/)
    assert.doesNotMatch(backups, /marginLeft:\s*['"]0\.5rem['"]/)
  })
})
