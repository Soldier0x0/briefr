import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ADMIN = path.join(path.dirname(fileURLToPath(import.meta.url)), 'AdminPage.jsx')

describe('Admin URL cleared when leaving a page via setPage', () => {
  it('setPage writes only p= when page changes; URL sync uses applyPageState', () => {
    const src = fs.readFileSync(ADMIN, 'utf8')
    assert.match(src, /ADMIN_PAGE_SCOPED_PARAMS/)
    assert.match(src, /const applyPageState = useCallback/)
    assert.match(src, /const setPage = useCallback/)
    // Changing page replaces the query with only p= (drops section/job_id/…).
    assert.match(
      src,
      /setSearchParams\(\(prev\) => \{[\s\S]*?prev\.get\('p'\) === id[\s\S]*?next\.set\('p', id\)/,
    )
    const syncStart = src.indexOf("const requested = searchParams.get('p')")
    const syncEnd = src.indexOf('function setupPolling')
    assert.ok(syncStart >= 0 && syncEnd > syncStart, 'URL→page sync block')
    const syncBlock = src.slice(syncStart, syncEnd)
    // Deep-link / refresh must not rewrite URL (preserve ingest filters).
    assert.match(syncBlock, /applyPageState\(requested\)/)
    assert.doesNotMatch(syncBlock, /setPage\(requested\)/)
  })
})
