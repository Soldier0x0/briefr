import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const CSS_PATH = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
  'pages',
  'security-architecture',
  'SecurityArchitecturePage.css',
)

function readCss() {
  return fs.readFileSync(CSS_PATH, 'utf8')
}

function blockForSelector(css, selector) {
  const re = new RegExp(`${selector.replace('.', '\\.')}\\s*\\{([^}]+)\\}`)
  return re.exec(css)?.[1] || ''
}

describe('PM-2d ARCH layout gate', () => {
  it('overview stat grid uses consistent tile gap and card hover affordance', () => {
    const css = readCss()
    const grid = blockForSelector(css, '.sa-stat-grid')
    const cardHover = css.match(/\.sa-stat-card-btn:hover\s+\.sa-stat-card\s*\{([^}]+)\}/)?.[1] || ''
    assert.match(grid, /gap:\s*16px/, 'overview tiles should use 16px gap')
    assert.match(cardHover, /border-color:\s*var\(--border-active\)/, 'tile hover should use border-active')
    assert.match(cardHover, /transform:/, 'tile hover should include subtle transform')
  })

  it('trust boundary cards use rounded layout and centered vertical flow', () => {
    const css = readCss()
    const card = blockForSelector(css, '.sa-tb-card')
    const flow = blockForSelector(css, '.sa-tb-flow')
    const step = blockForSelector(css, '.sa-tb-flow-step')
    assert.match(card, /border-radius:\s*12px/, 'trust cards should be rounded')
    assert.match(flow, /align-items:\s*center/, 'trust flow should center nodes')
    assert.match(step, /width:\s*100%/, 'trust flow steps should span card width for alignment')
    assert.match(css, /\.sa-tb-flow-arrow\s*\{[^}]*font-size:\s*1rem/, 'flow arrows should be sized for alignment')
  })
})
