import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), 'utf8')
}

describe('DateTimePicker v2 layout gate', () => {
  it('DateTimePicker.jsx uses card body/footer structure with clock icon', () => {
    const jsx = read('components/ui/DateTimePicker.jsx')
    assert.match(jsx, /ui-datetime-picker-card/)
    assert.match(jsx, /ui-datetime-picker-body/)
    assert.match(jsx, /ui-datetime-picker-footer/)
    assert.match(jsx, /Clock/)
    assert.match(jsx, /ui-datetime-picker-field-label/)
    assert.doesNotMatch(jsx, /Done/, 'Done button removed — popover closes on outside click')
  })

  it('DateTimePicker.css defines compact card popover with bordered time footer', () => {
    const css = read('components/ui/DateTimePicker.css')
    assert.match(css, /\.ui-datetime-picker-card\s*\{/)
    assert.match(css, /\.ui-datetime-picker-footer\s*\{[^}]*border-top:/)
    assert.match(css, /\.ui-datetime-picker-time-input\s*\{/)
    assert.match(css, /\.ui-datetime-picker-clock\s*\{/)
  })
})
