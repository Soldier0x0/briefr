import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { activityRowShowsPayloadActions } from './aiOperationsActivityActions.js'

describe('activityRowShowsPayloadActions', () => {
  it('returns false when row is missing', () => {
    assert.equal(activityRowShowsPayloadActions(null), false)
    assert.equal(activityRowShowsPayloadActions(undefined), false)
  })

  it('prefers payload_actionable when present', () => {
    assert.equal(
      activityRowShowsPayloadActions({ has_payload: true, payload_actionable: false }),
      false,
    )
    assert.equal(
      activityRowShowsPayloadActions({ has_payload: false, payload_actionable: true }),
      true,
    )
  })

  it('falls back to has_payload when payload_actionable is absent', () => {
    assert.equal(activityRowShowsPayloadActions({ has_payload: false }), false)
    assert.equal(activityRowShowsPayloadActions({ has_payload: true }), true)
  })
})
