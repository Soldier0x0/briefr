import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const CSS_PATH = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
  'components',
  'ui',
  'DataGrid.css',
)

function readCss() {
  return fs.readFileSync(CSS_PATH, 'utf8')
}

function paddingPx(block) {
  const m = block.match(/padding:\s*([^;]+);/)
  if (!m) return null
  const nums = m[1].match(/(\d+(?:\.\d+)?)px/g)
  if (!nums) return null
  return nums.map((n) => Number.parseFloat(n))
}

describe('PM-2b DataGrid standard gate', () => {
  it('DataGrid.css defines 8–12px cell padding on th and td', () => {
    const css = readCss()
    const thBlock = css.match(/\.data-grid-table\s+th\s*\{([^}]+)\}/)?.[1] || ''
    const tdBlock = css.match(/\.data-grid-table\s+td\s*\{([^}]+)\}/)?.[1] || ''
    assert.ok(thBlock, 'missing .data-grid-table th rule')
    assert.ok(tdBlock, 'missing .data-grid-table td rule')
    for (const px of [...paddingPx(thBlock), ...paddingPx(tdBlock)]) {
      assert.ok(px >= 8 && px <= 12, `cell padding ${px}px outside 8–12px standard`)
    }
  })

  it('DataGrid.css defines light row borders on body cells', () => {
    const css = readCss()
    assert.match(
      css,
      /\.data-grid-table\s+td\s*\{[^}]*border-bottom:\s*1px\s+solid\s+var\(--border\)/,
      'missing light row border on td',
    )
  })

  it('DataGrid.css keeps horizontal scroll on the grid wrapper', () => {
    const css = readCss()
    assert.match(
      css,
      /\.data-grid-scroll\s*\{[^}]*overflow-x:\s*auto/,
      'missing horizontal scroll on .data-grid-scroll',
    )
  })
})
