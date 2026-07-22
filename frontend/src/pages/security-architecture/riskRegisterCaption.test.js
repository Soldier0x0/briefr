import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const RISK_REGISTER = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  'sections',
  'RiskRegisterSection.jsx',
)

function read(file) {
  return fs.readFileSync(file, 'utf8')
}

describe('RiskRegisterSection live self-stack cap caption', () => {
  it('uses filtered live row count and hides when origin is curated', () => {
    const src = read(RISK_REGISTER)
    assert.match(src, /const liveVisible = rows\.filter\(r => r\.origin === 'live'\)\.length/)
    assert.match(src, /originFilter !== 'curated'/)
    assert.match(src, /liveSelfStack\.scored_matches > liveVisible/)
    assert.match(src, /live self-stack showing \$\{liveVisible\} of/)
    assert.doesNotMatch(src, /liveSelfStack\.admitted/)
  })
})
