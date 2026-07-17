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
})
