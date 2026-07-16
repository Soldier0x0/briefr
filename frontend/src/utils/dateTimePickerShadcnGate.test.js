import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:url'

function read(rel) {
  return fs.readFileSync(new URL(rel, import.meta.url), 'utf8')
}

describe('DateTimePicker shadcn option A gate', () => {
  it('uses card layout, native time input, clock icon — no selects or Done', () => {
    const jsx = read('../components/ui/DateTimePicker.jsx')
    assert.match(jsx, /ui-datetime-picker-card/)
    assert.match(jsx, /type="time"/)
    assert.match(jsx, /ui-datetime-picker-clock-leading/)
    assert.doesNotMatch(jsx, /from '\.\/Select\.jsx'/)
    assert.doesNotMatch(jsx, /\bDone\b/)
  })

  it('calendar uses body font, rounded hover, white selected day', () => {
    const css = read('../components/ui/DateTimePicker.css')
    assert.match(css, /font-family:\s*var\(--font-body/)
    assert.match(css, /\.ui-day-picker-selected\s+\.ui-day-picker-day-btn\s*\{[^}]*background:\s*var\(--text\)/)
    assert.match(css, /\.ui-day-picker-day-btn:hover:not\(:disabled\)\s*\{[^}]*border-radius:/)
  })
})
