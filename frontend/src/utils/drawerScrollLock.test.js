import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:url'

function read(rel) {
  return fs.readFileSync(new URL(rel, import.meta.url), 'utf8')
}

describe('drawerScrollLock', () => {
  it('exports nested-scroll-aware wheel handler', () => {
    const src = read('./drawerScrollLock.js')
    assert.match(src, /export function handleDrawerWheel/)
    assert.match(src, /overflowY === 'auto'/)
  })

  it('drawer wires handleDrawerWheel instead of inline panel-only trap', () => {
    const jsx = read('../components/DetailDrawer/index.jsx')
    assert.match(jsx, /handleDrawerWheel/)
    assert.doesNotMatch(jsx, /const atTop = scrollTop <= 0 && e\.deltaY < 0/)
  })

  it('code panel body contains scroll for nested YAML blocks', () => {
    const css = read('../components/CodePanel.css')
    assert.match(css, /\.code-panel-body[\s\S]*overflow-y:\s*auto/)
    assert.match(css, /overscroll-behavior:\s*contain/)
  })
})
