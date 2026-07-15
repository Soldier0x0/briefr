import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), 'utf8')
}

describe('Tooltip v2 Radix gate', () => {
  it('Tooltip.jsx uses @radix-ui/react-tooltip primitives', () => {
    const jsx = read('components/ui/Tooltip.jsx')
    assert.match(jsx, /@radix-ui\/react-tooltip/)
    assert.match(jsx, /TooltipProvider/)
    assert.match(jsx, /TooltipTrigger/)
    assert.match(jsx, /TooltipContent/)
  })

  it('app root wraps UI in TooltipProvider', () => {
    const main = read('main.jsx')
    assert.match(main, /TooltipProvider/)
  })

  it('tooltip content uses shadcn-style surface tokens', () => {
    const css = read('components/ui/ui.css')
    assert.match(css, /\.ui-tooltip-content\s*\{/)
    assert.match(css, /\.ui-tooltip-content\s*\{[^}]*background:\s*var\(--bg2\)/)
    assert.match(css, /\.ui-tooltip-content\s*\{[^}]*border:\s*1px solid var\(--border2\)/)
  })
})
