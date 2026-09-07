import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { LLM_ERROR_LABELS } from './circuitLabels.js'

describe('LLM_ERROR_LABELS', () => {
  it('labels dns and network', () => {
    assert.equal(LLM_ERROR_LABELS.dns, 'dns failure')
    assert.equal(LLM_ERROR_LABELS.network, 'network error')
    assert.equal(LLM_ERROR_LABELS.unknown, 'unknown error')
  })
})
