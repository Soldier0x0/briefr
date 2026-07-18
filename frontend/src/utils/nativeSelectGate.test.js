import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

const SKIP_FILES = new Set([
  'components/ui/Select.jsx', // Radix select primitive
  'components/ui/DateTimePicker.jsx', // datetime primitive — native select dropdowns by design
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

describe('E3-5 native select gate', () => {
  it('no native <select> elements remain in frontend/src', () => {
    const hits = []
    for (const file of walk(ROOT)) {
      const rel = path.relative(ROOT, file).split(path.sep).join('/')
      if (SKIP_FILES.has(rel)) continue
      const src = fs.readFileSync(file, 'utf8')
      if (/<select[\s/>]/.test(src)) {
        hits.push(rel)
      }
    }
    assert.deepEqual(
      hits.sort(),
      [],
      `native <select> found:\n${hits.join('\n')}`,
    )
  })
})
