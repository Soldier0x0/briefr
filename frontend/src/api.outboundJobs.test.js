import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { outboundJobsPath, outboundJobsPingPath } from './apiOutboundJobs.js'

describe('outboundJobsPath', () => {
  it('includes limit query', () => {
    assert.equal(outboundJobsPath(50), '/jobs/outbound?limit=50')
  })
  it('clamps limit to 1..200', () => {
    assert.equal(outboundJobsPath(0), '/jobs/outbound?limit=1')
    assert.equal(outboundJobsPath(999), '/jobs/outbound?limit=200')
  })

  it('returns the health ping canary path', () => {
    assert.equal(outboundJobsPingPath(), '/jobs/outbound/ping')
  })
})
