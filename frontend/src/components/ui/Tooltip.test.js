import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

describe('Tooltip module', () => {
  it('exports portaled Tooltip component (pre-Radix)', async () => {
    const src = await import('node:fs/promises').then(fs =>
      fs.readFile(new URL('./Tooltip.jsx', import.meta.url), 'utf8'),
    )
    assert.match(src, /export default function Tooltip/)
    assert.match(src, /createPortal/)
    assert.doesNotMatch(src, /@radix-ui\/react-tooltip/)
  })

  it('ControlTooltip defaults to hover-only trigger', async () => {
    const src = await import('node:fs/promises').then(fs =>
      fs.readFile(new URL('../ControlTooltip.jsx', import.meta.url), 'utf8'),
    )
    assert.match(src, /trigger\s*=\s*'hover'/)
  })
})
