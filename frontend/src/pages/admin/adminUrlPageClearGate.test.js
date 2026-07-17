import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ADMIN = path.join(path.dirname(fileURLToPath(import.meta.url)), 'AdminPage.jsx')

describe('Admin page owns URL (p=)', () => {
  it('setPage writes p via buildAdminPageSearchParams; URL sync uses applyPageState', () => {
    const src = fs.readFileSync(ADMIN, 'utf8')
    assert.match(src, /buildAdminPageSearchParams/)
    assert.match(src, /const applyPageState = useCallback/)
    assert.match(src, /const setPage = useCallback/)
    assert.match(src, /buildAdminPageSearchParams\(prev, id\)/)
    const syncStart = src.indexOf("const requested = searchParams.get('p')")
    const syncEnd = src.indexOf('function setupPolling')
    assert.ok(syncStart >= 0 && syncEnd > syncStart, 'URL→page sync block')
    const syncBlock = src.slice(syncStart, syncEnd)
    assert.match(syncBlock, /applyPageState\(requested\)/)
    assert.doesNotMatch(syncBlock, /setPage\(requested\)/)
  })
})
