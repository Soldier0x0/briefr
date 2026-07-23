import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  outboundStatusBadgeClass,
  outboundStatusHint,
  outboundStatusLabel,
} from './outboundJobStatus.js'

describe('outboundStatusLabel', () => {
  it('maps Procrastinate doing to RUNNING for operators', () => {
    assert.equal(outboundStatusLabel('doing'), 'RUNNING')
    assert.equal(outboundStatusLabel('DOING'), 'RUNNING')
  })

  it('maps todo to QUEUED', () => {
    assert.equal(outboundStatusLabel('todo'), 'QUEUED')
  })

  it('maps aborted to CANCELLED', () => {
    assert.equal(outboundStatusLabel('aborted'), 'CANCELLED')
  })

  it('uses analyst labels when requested', () => {
    assert.equal(outboundStatusLabel('doing', 'analyst'), 'In progress')
  })

  it('passes through unknown statuses', () => {
    assert.equal(outboundStatusLabel('custom'), 'custom')
  })
})

describe('outboundStatusBadgeClass', () => {
  it('uses info badge for running jobs', () => {
    assert.equal(outboundStatusBadgeClass('doing'), 'badge-info')
  })

  it('uses ok badge for succeeded jobs', () => {
    assert.equal(outboundStatusBadgeClass('succeeded'), 'badge-ok')
  })
})

describe('outboundStatusHint', () => {
  it('returns hint for known statuses', () => {
    assert.match(outboundStatusHint('doing'), /executing/i)
  })
})
