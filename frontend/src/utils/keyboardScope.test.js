import { afterEach, beforeEach, describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { hasTextSelection, shouldIgnoreGlobalShortcut } from './keyboardScope.js'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const DETAIL_DRAWER = path.join(ROOT, 'components', 'DetailDrawer', 'index.jsx')

const originalWindow = globalThis.window
const originalDocument = globalThis.document
const originalElement = globalThis.Element
const originalHTMLInputElement = globalThis.HTMLInputElement

class MockElement {
  constructor({ field = null, role = null, contentEditable = false } = {}) {
    this.field = field
    this.role = role
    this.isContentEditable = contentEditable
  }

  closest(selector) {
    if (this.field && selector.includes(this.field)) return this
    if (this.role && selector.includes(this.role)) return this
    if (this.isContentEditable && selector === '[contenteditable]') return this
    return null
  }
}

class MockInputElement extends MockElement {}

describe('keyboardScope', () => {
  beforeEach(() => {
    globalThis.window = undefined
    globalThis.document = undefined
    globalThis.Element = MockElement
    globalThis.HTMLInputElement = MockInputElement
  })

  afterEach(() => {
    globalThis.window = originalWindow
    globalThis.document = originalDocument
    globalThis.Element = originalElement
    globalThis.HTMLInputElement = originalHTMLInputElement
  })

  it('shouldIgnoreGlobalShortcut when IME composing', () => {
    assert.equal(shouldIgnoreGlobalShortcut({ isComposing: true, target: null }), true)
  })

  it('shouldIgnoreGlobalShortcut when a modifier key is pressed', () => {
    assert.equal(shouldIgnoreGlobalShortcut({ ctrlKey: true, isComposing: false, target: null }), true)
    assert.equal(shouldIgnoreGlobalShortcut({ metaKey: true, isComposing: false, target: null }), true)
    assert.equal(shouldIgnoreGlobalShortcut({ altKey: true, isComposing: false, target: null }), true)
  })

  it('shouldIgnoreGlobalShortcut when the target is editable', () => {
    const target = new MockInputElement({ field: 'input' })
    assert.equal(shouldIgnoreGlobalShortcut({ isComposing: false, target }), true)
  })

  it('hasTextSelection when a non-collapsed selection has text', () => {
    globalThis.window = {
      getSelection: () => ({
        isCollapsed: false,
        toString: () => 'selected text',
      }),
    }
    assert.equal(hasTextSelection(), true)
  })

  it('shouldIgnoreGlobalShortcut when the page has a text selection', () => {
    globalThis.window = {
      getSelection: () => ({
        isCollapsed: false,
        toString: () => 'selected text',
      }),
    }
    assert.equal(shouldIgnoreGlobalShortcut({ isComposing: false, target: null }), true)
  })

  it('hasTextSelection ignores collapsed or empty selections', () => {
    globalThis.window = {
      getSelection: () => ({
        isCollapsed: false,
        toString: () => '',
      }),
    }
    assert.equal(hasTextSelection(), false)

    globalThis.window = {
      getSelection: () => ({
        isCollapsed: true,
        toString: () => 'selected text',
      }),
    }
    assert.equal(hasTextSelection(), false)
  })

  it('shouldIgnoreGlobalShortcut allows navigation keys when not composing', () => {
    assert.equal(shouldIgnoreGlobalShortcut({ isComposing: false, target: null }), false)
  })

  it('DetailDrawer checks shortcut scope before preventing default copy behavior', () => {
    const src = fs.readFileSync(DETAIL_DRAWER, 'utf8')
    const start = src.indexOf('function onKey(e)')
    const end = src.indexOf("document.addEventListener('keydown', onKey)")
    assert.ok(start >= 0 && end > start, 'expected drawer key handler block markers')
    const block = src.slice(start, end)
    assert.match(block, /shouldIgnoreGlobalShortcut/)
    assert.match(block, /e\.key/)
    assert.ok(
      block.indexOf('shouldIgnoreGlobalShortcut') < block.indexOf('e.preventDefault()'),
      'shortcut scope guard should run before preventDefault',
    )
  })
})
