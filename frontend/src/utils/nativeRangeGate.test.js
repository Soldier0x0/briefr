import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

const SKIP_FILES = new Set([
  'components/ui/Slider.jsx', // primitive implementation
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

describe('E3-6 native range gate', () => {
  it('no native <input type="range"> elements remain in frontend/src', () => {
    const hits = []
    for (const file of walk(ROOT)) {
      const rel = path.relative(ROOT, file)
      if (SKIP_FILES.has(rel)) continue
      const src = fs.readFileSync(file, 'utf8')
      if (/type\s*=\s*["']range["']/.test(src)) {
        hits.push(rel)
      }
    }
    assert.deepEqual(
      hits.sort(),
      [],
      `native range inputs found:\n${hits.join('\n')}`,
    )
  })
})
