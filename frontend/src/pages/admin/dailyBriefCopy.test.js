import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { dailyBriefDeliveryCopy } from './dailyBriefCopy.js'

describe('dailyBriefDeliveryCopy', () => {
  it('alerts when nothing is subscribed', () => {
    const out = dailyBriefDeliveryCopy({ loading: false, error: null, labels: [] })
    assert.equal(out.kind, 'empty')
    assert.match(out.text, /Daily brief/i)
  })

  it('lists destination labels when subscribed', () => {
    const out = dailyBriefDeliveryCopy({
      loading: false,
      error: null,
      labels: ['discord'],
    })
    assert.equal(out.kind, 'ok')
    assert.match(out.text, /discord/)
  })
})
