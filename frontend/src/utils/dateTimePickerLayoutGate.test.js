import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), 'utf8')
}

describe('DateTimePicker shadcn match gate', () => {
  it('DateTimePicker uses native time input with leading clock icon (not hour/minute selects)', () => {
    const jsx = read('components/ui/DateTimePicker.jsx')
    assert.match(jsx, /type="time"/)
    assert.match(jsx, /step="1"/)
    assert.match(jsx, /ui-datetime-picker-time-native/)
    assert.doesNotMatch(jsx, /ui-datetime-picker-time-select/)
    assert.doesNotMatch(jsx, /from '\.\/Select\.jsx'/)
  })

  it('DateTimePicker.css styles rounded day hover and selected states', () => {
    const css = read('components/ui/DateTimePicker.css')
    assert.match(css, /\.ui-day-picker-day-btn:hover:not\(:disabled\)\s*\{[^}]*border-radius:/)
    assert.match(css, /\.ui-day-picker-selected\s+\.ui-day-picker-day-btn\s*\{[^}]*background:\s*var\(--text\)/)
    assert.match(css, /\.ui-datetime-picker-time-native/)
    assert.match(css, /webkit-calendar-picker-indicator/)
  })
})
