import { afterEach, beforeEach, describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { clearStalePointerState } from './clearPointerState.js'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const APP = path.join(ROOT, 'App.jsx')
const INTEL_TAB = path.join(ROOT, 'components', 'DetailDrawer', 'IntelTab.jsx')

const originalDocument = globalThis.document

describe('clearPointerState', () => {
  beforeEach(() => {
    globalThis.document = undefined
  })

  afterEach(() => {
    globalThis.document = originalDocument
  })

  it('does nothing when document is unavailable', () => {
    assert.equal(clearStalePointerState(), false)
  })

  it('blurs the active element when it lives inside a hidden panel', () => {
    let blurred = false
    globalThis.document = {
      activeElement: {
        closest: (selector) => (selector === '[hidden]' ? { hidden: true } : null),
        blur: () => {
          blurred = true
        },
      },
    }

    assert.equal(clearStalePointerState(), true)
    assert.equal(blurred, true)
  })

  it('leaves visible active elements alone', () => {
    let blurred = false
    globalThis.document = {
      activeElement: {
        closest: () => null,
        blur: () => {
          blurred = true
        },
      },
    }

    assert.equal(clearStalePointerState(), false)
    assert.equal(blurred, false)
  })

  it('wires tab changes through clearStalePointerState and keeps Intel campaign groups closed by default', () => {
    const app = fs.readFileSync(APP, 'utf8')
    assert.match(app, /import \{ clearStalePointerState \} from '\.\/utils\/clearPointerState\.js'/)
    assert.match(app, /const selectAppTab = useCallback/)
    assert.match(app, /clearStalePointerState\(/)

    const intel = fs.readFileSync(INTEL_TAB, 'utf8')
    assert.match(intel, /defaultOpen=\{false\}/)
  })
})
