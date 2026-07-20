import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { outboundJobsEmptyMessage } from './outboundJobsCopy.js'

describe('outboundJobsEmptyMessage', () => {
  it('explains when Procrastinate is disabled', () => {
    const message = outboundJobsEmptyMessage({ enabled: false })
    assert.match(message, /PROCRASTINATE_ENABLED=0/i)
    assert.match(message, /enable and restart/i)
  })

  it('is neutral when enabled but queue is empty', () => {
    assert.equal(outboundJobsEmptyMessage({ enabled: true }), 'No durable jobs yet.')
  })
})
