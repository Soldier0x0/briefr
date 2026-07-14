import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

describe('motion.js', () => {
  it('exports data-motion aware helpers', async () => {
    const src = await import('node:fs/promises').then(fs =>
      fs.readFile(new URL('./motion.js', import.meta.url), 'utf8'),
    )
    assert.match(src, /data-motion/)
    assert.match(src, /export function prefersReducedMotion/)
  })

  it('displayPrefsCore wires data-motion from reduceMotion', async () => {
    const src = await import('node:fs/promises').then(fs =>
      fs.readFile(new URL('./displayPrefsCore.js', import.meta.url), 'utf8'),
    )
    assert.match(src, /setAttribute\('data-motion', 'off'\)/)
    assert.match(src, /setAttribute\('data-motion', 'on'\)/)
  })
})
