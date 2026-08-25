import { readFileSync } from 'node:fs'
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

const source = readFileSync(new URL('../pages/WallboardPage.jsx', import.meta.url), 'utf8')

describe('Wallboard auto-token bootstrap gate', () => {
  it('waits for public config before loading wallboard data', () => {
    assert.match(source, /const \[configReady, setConfigReady\] = useState\(false\)/)
    assert.match(source, /setConfigReady\(true\)/)
    assert.match(source, /if \(!configReady\) return/)
    assert.match(source, /\[configReady, tryAutoToken\]/)
    assert.match(source, /useVisibilityAwareInterval\(\s*load,/)
    assert.match(source, /Number\(pollSeconds\) > 0 \? Number\(pollSeconds\) \* 1000 : POLL_MS/)
    assert.match(source, /enabled:\s*configReady/)
  })
})
