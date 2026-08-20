import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { createCameraController } from './investigateCameraController.js'
import { computePointCloudBounds } from './architectureGraphView.js'

describe('createCameraController', () => {
  it('reaches flyToView target after duration', () => {
    const cam = createCameraController({ x: 0, y: 0, scale: 1 })
    cam.flyToView({ x: 100, y: 40, scale: 2 }, { durationMs: 280 })
    cam.tick(280)
    const view = cam.getDisplayView()
    assert.equal(view.x, 100)
    assert.equal(view.y, 40)
    assert.equal(view.scale, 2)
    assert.equal(cam.isAnimating(), false)
  })

  it('centers flyToBounds on the point cloud', () => {
    const cam = createCameraController({ x: 0, y: 0, scale: 1 })
    const bounds = computePointCloudBounds([{ x: 400, y: 300 }, { x: 420, y: 310 }], 8, 20)
    cam.flyToBounds(bounds, 800, 600)
    cam.tick(280)
    const view = cam.getDisplayView()
    const cx = (bounds.minX + bounds.maxX) / 2
    const cy = (bounds.minY + bounds.maxY) / 2
    assert.ok(Math.abs(view.x + cx * view.scale - 400) < 2)
    assert.ok(Math.abs(view.y + cy * view.scale - 300) < 2)
  })

  it('decays pan inertia to rest', () => {
    const cam = createCameraController({ x: 0, y: 0, scale: 1 })
    cam.nudgePanVelocity(20, 0)
    for (let i = 0; i < 80; i += 1) cam.tick(16)
    assert.equal(cam.isAnimating(), false)
  })

  it('skips animation when reducedMotion is set', () => {
    const cam = createCameraController({ x: 0, y: 0, scale: 1 }, { reducedMotion: true })
    cam.flyToView({ x: 50, y: 10, scale: 1.5 })
    const view = cam.getDisplayView()
    assert.equal(view.x, 50)
    assert.equal(view.scale, 1.5)
    assert.equal(cam.isAnimating(), false)
  })
})
