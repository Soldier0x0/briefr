import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

const SKIP_FILES = new Set([
  'components/ui/Button.jsx', // primitive — callers supply aria-label
])

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name)
    const st = fs.statSync(p)
    if (st.isDirectory() && name !== 'node_modules') walk(p, out)
    else if (/\.jsx?$/.test(name)) out.push(p)
  }
  return out
}

/** Button body is icon/symbol-only (no visible words). */
function isIconOnlyBody(body) {
  const text = body
    .replace(/<[^>]+>/g, '')
    .replace(/\{[^}]+\}/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (text && /[A-Za-z]{2,}/.test(text)) return false
  if (text && !/^[✕×↑↓•….\-&;]+$/.test(text) && text !== '&middot;&middot;&middot;') {
    return false
  }
  return (
    !text
    || /^[✕×↑↓•….\-]+$/.test(text)
    || text === '&middot;&middot;&middot;'
    || /<[A-Z][A-Za-z0-9]*\s+[^>]*size=/.test(body)
  )
}

describe('E6-3 icon-only aria-label gate', () => {
  it('icon-only <button> elements declare aria-label', () => {
    const misses = []
    for (const file of walk(ROOT)) {
      const rel = path.relative(ROOT, file)
      if (SKIP_FILES.has(rel)) continue
      const src = fs.readFileSync(file, 'utf8')
      const re = /<button\b([^>]*)>([\s\S]*?)<\/button>/g
      let m
      while ((m = re.exec(src))) {
        const attrs = m[1]
        const body = m[2]
        if (/\{/.test(body.trim())) continue // dynamic children — not statically verifiable
        if (!isIconOnlyBody(body)) continue
        if (/aria-label=/.test(attrs) || /aria-labelledby=/.test(attrs)) continue
        misses.push(rel)
      }
    }
    assert.deepEqual(
      [...new Set(misses)].sort(),
      [],
      `icon-only buttons missing aria-label:\n${[...new Set(misses)].join('\n')}`,
    )
  })
})
