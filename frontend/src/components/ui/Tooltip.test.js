import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

describe('Tooltip module', () => {
  it('exports Radix-based Tooltip primitives', async () => {
    const src = await import('node:fs/promises').then(fs =>
      fs.readFile(new URL('./Tooltip.jsx', import.meta.url), 'utf8'),
    )
    assert.match(src, /export default function Tooltip/)
    assert.match(src, /@radix-ui\/react-tooltip/)
    assert.match(src, /export function TooltipProvider/)
    assert.match(src, /export function TooltipContent/)
  })

  it('ControlTooltip defaults to hover-only trigger', async () => {
    const src = await import('node:fs/promises').then(fs =>
      fs.readFile(new URL('../ControlTooltip.jsx', import.meta.url), 'utf8'),
    )
    assert.match(src, /trigger\s*=\s*'hover'/)
  })
})
