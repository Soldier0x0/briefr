import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

/**
 * Tooltip coordinator and trigger modes are exercised via module shape;
 * full DOM portal behavior is validated in Playwright smoke when enabled.
 */
describe('Tooltip module', () => {
  it('exports default Tooltip component', async () => {
    const src = await import('node:fs/promises').then(fs =>
      fs.readFile(new URL('./Tooltip.jsx', import.meta.url), 'utf8'),
    )
    assert.match(src, /export default function Tooltip/)
  })

  it('ControlTooltip defaults to hover-only trigger', async () => {
    const src = await import('node:fs/promises').then(fs =>
      fs.readFile(new URL('../ControlTooltip.jsx', import.meta.url), 'utf8'),
    )
    assert.match(src, /trigger\s*=\s*'hover'/)
  })
})
