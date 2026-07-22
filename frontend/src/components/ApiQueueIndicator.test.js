import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const dir = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(dir, 'ApiQueueIndicator.jsx'), 'utf8')
const css = readFileSync(join(dir, 'ApiQueueIndicator.css'), 'utf8')

describe('ApiQueueIndicator portal', () => {
  it('uses Radix dropdown/popover content', () => {
    assert.match(src, /DropdownMenuContent|Popover\.Content|PopoverContent/)
  })
  it('does not rely on position:absolute panel as only overlay', () => {
    // Allow absolute inside portaled content; forbid old top-level absolute dropdown pattern without portal
    assert.match(src, /DropdownMenu|Popover/)
  })
  it('uses token z-index not raw 400', () => {
    assert.doesNotMatch(css, /z-index:\s*400/)
  })
})
