import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const APP = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'App.jsx')

describe('Analyst shell tab owns URL (tab=)', () => {
  it('selectAppTab writes tab via buildAppTabSearchParams with pushContext', () => {
    const src = fs.readFileSync(APP, 'utf8')
    assert.match(src, /buildAppTabSearchParams/)
    assert.match(src, /resolveAppTab/)
    assert.match(src, /const selectAppTab = useCallback/)
    assert.match(src, /pushContext\(setSearchParams,\s*\(prev\) => buildAppTabSearchParams\(prev, tab\)\)/)
    assert.match(src, /setActiveTab=\{selectAppTab\}/)
  })

  it('?cve= sync keeps drawer URL and uses replaceHygiene for tab hygiene only', () => {
    const src = fs.readFileSync(APP, 'utf8')
    assert.match(src, /openDrawerCveIdRef/)
    assert.match(src, /replaceHygiene\(setSearchParams/)
    assert.match(src, /pushContext\(setSearchParams/)
    assert.match(src, /next\.set\('cve', id\)/)
    assert.doesNotMatch(src, /window\.location\.assign/)
    const start = src.indexOf('// URL ↔ drawer')
    const end = src.indexOf('const iocDeepLinkHandled')
    assert.ok(start >= 0 && end > start, 'cve URL sync block markers')
    const block = src.slice(start, end)
    assert.match(block, /buildAppTabSearchParams\(prev, 'feed'\)/)
    assert.doesNotMatch(block, /selectAppTab\('feed'\)/)
  })
})
