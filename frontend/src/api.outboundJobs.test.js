import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { outboundJobsPath } from './apiOutboundJobs.js'

describe('outboundJobsPath', () => {
  it('includes limit query', () => {
    assert.equal(outboundJobsPath(50), '/api/admin/jobs/outbound?limit=50')
  })
  it('clamps limit to 1..200', () => {
    assert.equal(outboundJobsPath(0), '/api/admin/jobs/outbound?limit=1')
    assert.equal(outboundJobsPath(999), '/api/admin/jobs/outbound?limit=200')
  })
})
