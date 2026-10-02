import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  cameraActionForStructuralChange,
  structuralReasonForExpand,
} from './investigateCameraPolicy.js'

describe('cameraActionForStructuralChange', () => {
  it('maps expand to fly_neighborhood', () => {
    assert.equal(cameraActionForStructuralChange('expand'), 'fly_neighborhood')
  })

  it('maps load_more to fly_neighborhood', () => {
    assert.equal(cameraActionForStructuralChange('load_more'), 'fly_neighborhood')
  })

  it('maps resolve to fit_all', () => {
    assert.equal(cameraActionForStructuralChange('resolve'), 'fit_all')
  })

  it('maps filter to fit_visible', () => {
    assert.equal(cameraActionForStructuralChange('filter'), 'fit_visible')
  })
})

describe('structuralReasonForExpand', () => {
  it('returns load_more when cursor param present', () => {
    assert.equal(structuralReasonForExpand({ cursor: 'abc' }), 'load_more')
  })

  it('returns expand without cursor', () => {
    assert.equal(structuralReasonForExpand({}), 'expand')
    assert.equal(structuralReasonForExpand(null), 'expand')
  })
})
