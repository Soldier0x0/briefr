import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { createDragTracker } from './investigateDragPolicy.js'

describe('createDragTracker', () => {
  it('treats sub-threshold movement as click', () => {
    const tracker = createDragTracker(4)
    tracker.start(0, 0)
    assert.equal(tracker.move(2, 1), 'pending')
    assert.equal(tracker.end(), 'click')
  })

  it('promotes over-threshold movement to drag', () => {
    const tracker = createDragTracker(4)
    tracker.start(0, 0)
    assert.equal(tracker.move(10, 0), 'drag')
    assert.equal(tracker.end(), 'drag')
  })

  it('stays drag after threshold is crossed', () => {
    const tracker = createDragTracker(4)
    tracker.start(0, 0)
    tracker.move(10, 0)
    assert.equal(tracker.move(11, 0), 'drag')
  })
})
