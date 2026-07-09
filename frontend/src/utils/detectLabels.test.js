import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { confidenceMatchLabel } from './detectLabels.js'

describe('detectLabels', () => {
  it('uses sentence-case confidence labels', () => {
    assert.equal(confidenceMatchLabel('HIGH'), 'High confidence match')
    assert.equal(confidenceMatchLabel('MEDIUM'), 'Medium confidence match')
    assert.equal(confidenceMatchLabel('LOW'), 'Low confidence match')
  })
})
