import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  clampScale,
  computeFitView,
  computeGraphBounds,
  zoomAtCursor,
} from './architectureGraphView.js'

describe('zoomAtCursor', () => {
  it('keeps the graph point under the cursor fixed when zooming in', () => {
    const view = { x: 40, y: 20, scale: 1 }
    const cursorX = 200
    const cursorY = 150
    const beforeGraphX = (cursorX - view.x) / view.scale
    const beforeGraphY = (cursorY - view.y) / view.scale

    const next = zoomAtCursor(view, cursorX, cursorY, 1.25)

    const afterGraphX = (cursorX - next.x) / next.scale
    const afterGraphY = (cursorY - next.y) / next.scale
    assert.ok(next.scale > view.scale)
    assert.ok(Math.abs(afterGraphX - beforeGraphX) < 0.001)
    assert.ok(Math.abs(afterGraphY - beforeGraphY) < 0.001)
  })

  it('clamps scale at max zoom without changing translate when already at max', () => {
    const view = { x: 10, y: 10, scale: 4 }
    const next = zoomAtCursor(view, 100, 100, 1.2)
    assert.equal(next.scale, 4)
    assert.equal(next.x, view.x)
    assert.equal(next.y, view.y)
  })
})

describe('computeGraphBounds', () => {
  it('includes node width and height with padding', () => {
    const positioned = [{ x: 20, y: 56 }]
    const bounds = computeGraphBounds(positioned, 260, 26, 10)
    assert.equal(bounds.minX, 10)
    assert.equal(bounds.minY, 46)
    assert.equal(bounds.maxX, 290)
    assert.equal(bounds.maxY, 92)
  })
})

describe('computeFitView', () => {
  it('frames all nodes inside the viewport', () => {
    const bounds = { minX: 0, minY: 0, maxX: 1000, maxY: 800 }
    const fit = computeFitView(bounds, 500, 400)
    const corners = [
      { x: bounds.minX, y: bounds.minY },
      { x: bounds.maxX, y: bounds.minY },
      { x: bounds.minX, y: bounds.maxY },
      { x: bounds.maxX, y: bounds.maxY },
    ]
    for (const corner of corners) {
      const screenX = fit.x + corner.x * fit.scale
      const screenY = fit.y + corner.y * fit.scale
      assert.ok(screenX >= -1, `left edge should be visible (${screenX})`)
      assert.ok(screenY >= -1, `top edge should be visible (${screenY})`)
      assert.ok(screenX <= 501, `right edge should be visible (${screenX})`)
      assert.ok(screenY <= 401, `bottom edge should be visible (${screenY})`)
    }
  })

  it('centers content in the viewport', () => {
    const bounds = { minX: 100, minY: 100, maxX: 300, maxY: 300 }
    const fit = computeFitView(bounds, 400, 400)
    const centerGraphX = (bounds.minX + bounds.maxX) / 2
    const centerGraphY = (bounds.minY + bounds.maxY) / 2
    const screenCenterX = fit.x + centerGraphX * fit.scale
    const screenCenterY = fit.y + centerGraphY * fit.scale
    assert.ok(Math.abs(screenCenterX - 200) < 1)
    assert.ok(Math.abs(screenCenterY - 200) < 1)
  })
})

describe('clampScale', () => {
  it('clamps below minimum and above maximum', () => {
    assert.equal(clampScale(0.1), 0.4)
    assert.equal(clampScale(10), 4)
    assert.equal(clampScale(1.5), 1.5)
  })
})
