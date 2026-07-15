import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

/** PM-2a: neutral selection/toggle affordances must not use danger red. */
const SELECTION_SELECTOR =
  /(\.toggle-on\b|\.technique-row-active\b|\.tz-item-active\b|:checked\s*~|:checked\s*\+)/i

const FORBIDDEN_IN_SELECTION = [
  /\bvar\(--red\)/,
  /\bvar\(--red-dim\)/,
  /--red\b/,
  /--red-dim\b/,
]

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name)
    const st = fs.statSync(p)
    if (st.isDirectory() && name !== 'node_modules') walk(p, out)
    else if (/\.css$/.test(name)) out.push(p)
  }
  return out
}

function extractRuleBlocks(css) {
  const blocks = []
  let i = 0
  while (i < css.length) {
    const brace = css.indexOf('{', i)
    if (brace === -1) break
    const selector = css.slice(i, brace).trim()
    let depth = 1
    let j = brace + 1
    while (j < css.length && depth > 0) {
      if (css[j] === '{') depth += 1
      else if (css[j] === '}') depth -= 1
      j += 1
    }
    const body = css.slice(brace + 1, j - 1)
    blocks.push({ selector, body })
    i = j
  }
  return blocks
}

describe('PM-2a selection accent gate', () => {
  it('toggle/selection/checked rules do not use danger red tokens', () => {
    const hits = []
    for (const file of walk(ROOT)) {
      const rel = path.relative(ROOT, file)
      const css = fs.readFileSync(file, 'utf8')
      for (const { selector, body } of extractRuleBlocks(css)) {
        if (!SELECTION_SELECTOR.test(selector)) continue
        if (selector.includes(':active') && !selector.includes('-active') && !selector.includes('toggle-on')) {
          continue
        }
        for (const pattern of FORBIDDEN_IN_SELECTION) {
          if (pattern.test(body)) {
            hits.push(`${rel}: ${selector.trim()}`)
            break
          }
        }
      }
    }
    assert.deepEqual(
      hits.sort(),
      [],
      `selection/toggle rules still use red (use accent tokens per PM-2a):\n${hits.join('\n')}`,
    )
  })
})
