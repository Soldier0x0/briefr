import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

describe('IOCLookup shell size', () => {
  it('keeps IOCLookup.jsx under the component LOC audit gate', async () => {
    const source = await readFile(new URL('../IOCLookup.jsx', import.meta.url), 'utf8')
    const lineCount = source.split(/\r?\n/).length

    assert.ok(lineCount < 600, `IOCLookup.jsx has ${lineCount} lines; expected < 600`)
  })
})
