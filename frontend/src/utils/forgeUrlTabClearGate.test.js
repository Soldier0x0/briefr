import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const APP = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'App.jsx')

describe('Forge URL cleared when leaving Forge tab', () => {
  it('selectAppTab deletes view/technique/pack when tab !== forge', () => {
    const src = fs.readFileSync(APP, 'utf8')
    assert.match(src, /const selectAppTab = useCallback/)
    assert.match(src, /tab === 'forge'/)
    assert.match(src, /next\.delete\('view'\)/)
    assert.match(src, /next\.delete\('technique'\)/)
    assert.match(src, /next\.delete\('pack'\)/)
    assert.match(src, /setActiveTab=\{selectAppTab\}/)
    // Deep-link into Forge must still use raw setActiveTab so params are kept.
    assert.match(src, /openForgeTechnique:[\s\S]*setActiveTab\('forge'\)/)
  })

  it('?cve= deep link clears Forge params in one setSearchParams', () => {
    const src = fs.readFileSync(APP, 'utf8')
    const start = src.indexOf('const deepLinkHandled = useRef(null)')
    const end = src.indexOf('// Forge owns ?view=')
    assert.ok(start >= 0 && end > start, 'cve deep-link block markers')
    const block = src.slice(start, end)
    // Avoid selectAppTab + setSearchParams in the same tick (RR overwrite).
    assert.match(block, /setActiveTab\('feed'\)/)
    assert.match(block, /next\.delete\('cve'\)/)
    assert.match(block, /next\.delete\('view'\)/)
    assert.match(block, /next\.delete\('technique'\)/)
    assert.match(block, /next\.delete\('pack'\)/)
    assert.doesNotMatch(block, /selectAppTab\('feed'\)/)
  })
})
