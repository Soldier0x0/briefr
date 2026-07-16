import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

const SKIP_FILES = new Set([
  'components/ui/DateTimePicker.jsx', // primitive — datetime select dropdowns live here
])

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name)
    const st = fs.statSync(p)
    if (st.isDirectory() && name !== 'node_modules') walk(p, out)
    else if (/\.jsx$/.test(name)) out.push(p)
  }
  return out
}

describe('DateTimePicker product standard gate', () => {
  it('no native datetime-local or date inputs outside DateTimePicker primitive', () => {
    const hits = []
    for (const file of walk(ROOT)) {
      const rel = path.relative(ROOT, file)
      if (SKIP_FILES.has(rel)) continue
      const src = fs.readFileSync(file, 'utf8')
      if (/type\s*=\s*["']datetime-local["']/.test(src)) hits.push(`${rel}: datetime-local`)
      if (/type\s*=\s*["']date["']/.test(src)) hits.push(`${rel}: date`)
      if (/type\s*=\s*["']time["']/.test(src)) hits.push(`${rel}: time`)
    }
    assert.deepEqual(
      hits.sort(),
      [],
      `use DateTimePicker / DateTimeRangeField instead of:\n${hits.join('\n')}`,
    )
  })

  it('datetime range surfaces import DateTimeRangeField from ui', () => {
    const consumers = [
      'components/TimeWindowPicker.jsx',
      'pages/admin/IngestLogPage.jsx',
    ]
    for (const rel of consumers) {
      const src = fs.readFileSync(path.join(ROOT, rel), 'utf8')
      assert.match(
        src,
        /DateTimeRangeField/,
        `${rel} must use DateTimeRangeField for custom datetime ranges`,
      )
    }
  })
})
