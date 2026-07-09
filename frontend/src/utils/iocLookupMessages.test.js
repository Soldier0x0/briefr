import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { IOC_NOT_FOUND_IN_DATABASES } from './iocLookupMessages.js'

describe('iocLookupMessages', () => {
  it('uses one consistent not-found phrase for configured sources', () => {
    assert.equal(
      IOC_NOT_FOUND_IN_DATABASES,
      'Not found in configured threat databases.',
    )
  })
})
