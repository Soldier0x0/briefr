import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const DATA_GRID_PATH = path.join(ROOT, 'src', 'components', 'ui', 'DataGrid.jsx')

describe('DataGrid TanStack Table v9 compatibility', () => {
  it('uses the official v8 compatibility adapter exported by Table v9', () => {
    const source = fs.readFileSync(DATA_GRID_PATH, 'utf8')

    assert.match(source, /from '@tanstack\/react-table\/legacy'/)
    assert.match(source, /useLegacyTable/)
    assert.doesNotMatch(source, /useReactTable/)
  })
})
