import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:url'

function read(rel) {
  return fs.readFileSync(new URL(rel, import.meta.url), 'utf8')
}

describe('DateTimeRangeField', () => {
  it('exports dual-input range field with start/end DateTimePickers', () => {
    const jsx = read('../components/ui/DateTimeRangeField.jsx')
    assert.match(jsx, /export default function DateTimeRangeField/)
    assert.match(jsx, /ui-datetime-range-start/)
    assert.match(jsx, /ui-datetime-range-end/)
    assert.match(jsx, /ui-datetime-range-sep/)
  })
})

describe('drawer UX fixes gate', () => {
  it('severity badge tooltip uses hover-only trigger (no focus flash on open)', () => {
    const jsx = read('../components/DetailDrawer/index.jsx')
    assert.match(jsx, /text=\{severityTooltip\([^)]+\)\}[\s\S]*?trigger="hover"/)
  })

  it('drawer tab panel contains scroll at boundaries', () => {
    const css = read('../components/DetailDrawer.css')
    assert.match(css, /\.drawer-tab-panel\s*\{[^}]*overscroll-behavior:\s*contain/)
  })

  it('tooltip uses opaque portal bubble (not Radix content)', () => {
    const jsx = read('../components/ui/Tooltip.jsx')
    const css = read('../components/ui/ui.css')
    assert.doesNotMatch(jsx, /@radix-ui\/react-tooltip/)
    assert.match(css, /\.ui-tooltip-bubble\s*\{[^}]*background:\s*var\(--bg3\)/)
  })
})
