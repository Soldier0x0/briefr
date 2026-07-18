import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

describe('FEED / EPSS movers UI cleanup gate', () => {
  it('EPSS movers TimeWindowPicker disables Custom range (API hours-only, max 168)', () => {
    const src = fs.readFileSync(path.join(ROOT, 'components/BriefCharts.jsx'), 'utf8')
    assert.match(src, /allowCustom=\{false\}/)
    assert.match(src, /EPSS_MOVERS_PRESET_IDS/)
    assert.doesNotMatch(
      src,
      /presetIds=\{TIME_PRESETS/,
      'EPSS movers must not expose the full TIME_PRESETS list (30d/90d exceed API le=168)',
    )
  })

  it('TimeWindowPicker supports allowCustom to hide dead Custom range…', () => {
    const src = fs.readFileSync(path.join(ROOT, 'components/TimeWindowPicker.jsx'), 'utf8')
    assert.match(src, /allowCustom\s*=\s*true/)
    assert.match(src, /allowCustom \? \[\{ value: CUSTOM_VALUE/)
  })

  it('EPSS movers header and rows share one CSS grid (no table colspan layout)', () => {
    const css = fs.readFileSync(path.join(ROOT, 'components/BriefCharts.css'), 'utf8')
    const jsx = fs.readFileSync(path.join(ROOT, 'components/BriefCharts.jsx'), 'utf8')
    assert.match(css, /--brief-epss-cols:/)
    assert.match(css, /\.brief-epss-cols\s*\{[^}]*display:\s*grid/s)
    assert.match(css, /\.brief-epss-head\b/)
    assert.match(jsx, /className="brief-epss-grid"/)
    assert.match(jsx, /brief-epss-cols brief-epss-head/)
    assert.doesNotMatch(jsx, /colSpan=\{4\}/)
    assert.match(css, /\.brief-epss-sev\s*\{[^}]*justify-content:\s*flex-start/s)
  })

  it('STACK local sync uses nextLocalStack (trim must not yank caret)', () => {
    const src = fs.readFileSync(path.join(ROOT, 'components/FilterBar.jsx'), 'utf8')
    assert.match(src, /nextLocalStack/)
  })

  it('FEED search and STACK inputs use surface-input (not page-blending bg2)', () => {
    const css = fs.readFileSync(path.join(ROOT, 'components/FilterBar.css'), 'utf8')
    assert.match(css, /\.filter-search\s*\{[^}]*background:\s*var\(--surface-input\)/s)
    assert.match(css, /\.filter-stack-input\s*\{[^}]*background:\s*var\(--surface-input\)/s)
    assert.match(css, /\.filter-search\s*\{[^}]*border:\s*1px solid var\(--border2\)/s)
  })

  it('Watchlist empty copy does not instruct analysts to snooze from the feed', () => {
    const src = fs.readFileSync(path.join(ROOT, 'pages/admin/WatchlistPage.jsx'), 'utf8')
    assert.doesNotMatch(src, /pin or snooze CVEs from the main feed/)
  })
})
