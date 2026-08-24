import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

describe('Popover module', () => {
  it('exports portaled Radix PopoverContent', async () => {
    const src = await import('node:fs/promises').then(fs =>
      fs.readFile(new URL('./Popover.jsx', import.meta.url), 'utf8'),
    )
    assert.match(src, /@radix-ui\/react-popover/)
    assert.match(src, /RadixPopover\.Portal/)
    assert.match(src, /ui-popover-content/)
    assert.match(src, /export const PopoverContent/)
  })

  it('styles popover content with design tokens', async () => {
    const src = await import('node:fs/promises').then(fs =>
      fs.readFile(new URL('./ui.css', import.meta.url), 'utf8'),
    )
    assert.match(src, /\.ui-popover-content[\s\S]*var\(--shadow-overlay\)/)
    assert.match(src, /\.ui-popover-content[\s\S]*var\(--border2\)/)
    assert.match(src, /\.ui-popover-content[\s\S]*var\(--radius-sm\)/)
    assert.match(src, /\.ui-popover-content[\s\S]*var\(--z-dropdown\)/)
    assert.match(src, /\.ui-popover-content:focus-visible[\s\S]*var\(--focus-ring\)/)
  })

  it('re-exports from ui index', async () => {
    const src = await import('node:fs/promises').then(fs =>
      fs.readFile(new URL('./index.js', import.meta.url), 'utf8'),
    )
    assert.match(src, /PopoverContent/)
    assert.match(src, /PopoverTrigger/)
  })
})
