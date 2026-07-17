import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const APP = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'App.jsx')

describe('Analyst shell tab owns URL (tab=)', () => {
  it('selectAppTab writes tab via buildAppTabSearchParams', () => {
    const src = fs.readFileSync(APP, 'utf8')
    assert.match(src, /buildAppTabSearchParams/)
    assert.match(src, /resolveAppTab/)
    assert.match(src, /const selectAppTab = useCallback/)
    assert.match(src, /buildAppTabSearchParams\(prev, tab\)/)
    assert.match(src, /setActiveTab=\{selectAppTab\}/)
  })

  it('?cve= deep link uses buildAppTabSearchParams(feed) in one setSearchParams', () => {
    const src = fs.readFileSync(APP, 'utf8')
    const start = src.indexOf('const deepLinkHandled = useRef(null)')
    const end = src.indexOf('// Keep React tab state')
    assert.ok(start >= 0 && end > start, 'cve deep-link block markers')
    const block = src.slice(start, end)
    assert.match(block, /setActiveTab\('feed'\)/)
    assert.match(block, /buildAppTabSearchParams\(prev, 'feed'\)/)
    assert.doesNotMatch(block, /selectAppTab\('feed'\)/)
  })
})
