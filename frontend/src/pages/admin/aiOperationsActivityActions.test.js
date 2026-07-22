import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { activityRowHasPayload } from './aiOperationsActivityActions.js'

describe('activityRowHasPayload', () => {
  it('returns false when row is missing', () => {
    assert.equal(activityRowHasPayload(null), false)
    assert.equal(activityRowHasPayload(undefined), false)
  })

  it('returns false when payload flag is falsey', () => {
    assert.equal(activityRowHasPayload({ has_payload: false }), false)
    assert.equal(activityRowHasPayload({ has_payload: 0 }), false)
  })

  it('returns true when payload flag is truthy', () => {
    assert.equal(activityRowHasPayload({ has_payload: true }), true)
    assert.equal(activityRowHasPayload({ has_payload: 1 }), true)
  })
})
