import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'

describe('Sidebar filters', () => {
  it('uses shared Switch for Your Filters toggles', async () => {
    const src = await fs.readFile(new URL('./Sidebar.jsx', import.meta.url), 'utf8')
    assert.match(src, /import Switch from '\.\/ui\/Switch\.jsx'/)
    assert.doesNotMatch(src, /function Toggle\(/)
    assert.match(src, /<Switch[\s\S]*label=\{def\.label\}/)
  })
})
