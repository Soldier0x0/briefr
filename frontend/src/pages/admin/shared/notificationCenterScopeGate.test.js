import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const src = fs.readFileSync(
  path.join(path.dirname(fileURLToPath(import.meta.url)), 'NotificationCenter.jsx'),
  'utf8',
)

describe('NotificationCenter scope gate', () => {
  it('derives scope from user role via useAuth, not a hardcoded scope="all"', () => {
    assert.match(src, /useAuth/)
    assert.match(src, /user\?\.role === 'admin'/)
    assert.match(src, /'all'/)
    assert.match(src, /'analyst'/)
    assert.match(src, /scope=\{notificationScope\}/)
    assert.doesNotMatch(src, /scope="all"/)
  })
})
