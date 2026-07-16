import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'

function read(rel) {
  return fs.readFileSync(new URL(rel, import.meta.url), 'utf8')
}

describe('DateTimePicker simple dropdown gate', () => {
  it('uses DD-MM-YY HH:mm:ss display and native select dropdowns', () => {
    const jsx = read('../components/ui/DateTimePicker.jsx')
    const css = read('../components/ui/DateTimePicker.css')
    assert.match(jsx, /formatDatetimeDisplay/)
    assert.match(jsx, /<select/)
    assert.match(jsx, /ui-datetime-picker-panel/)
    assert.doesNotMatch(jsx, /react-day-picker/)
    assert.doesNotMatch(jsx, /date-fns/)
    assert.doesNotMatch(jsx, /DayPicker/)
    assert.doesNotMatch(jsx, /type="time"/)
    assert.match(css, /\.ui-datetime-select\b/)
    assert.doesNotMatch(css, /ui-day-picker/)
  })
})
