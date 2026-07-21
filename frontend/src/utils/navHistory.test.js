import { describe, it, mock } from 'node:test'
import assert from 'node:assert/strict'
import { pushContext, replaceHygiene } from './navHistory.js'

function params(obj = {}) {
  return new URLSearchParams(obj)
}

describe('navHistory', () => {
  it('pushContext calls setSearchParams with replace:false', () => {
    const setSearchParams = mock.fn()
    const mutator = (prev) => {
      const next = new URLSearchParams(prev)
      next.set('tab', 'forge')
      return next
    }
    pushContext(setSearchParams, mutator)
    assert.equal(setSearchParams.mock.calls.length, 1)
    const [fn, opts] = setSearchParams.mock.calls[0].arguments
    assert.equal(typeof fn, 'function')
    assert.deepEqual(opts, { replace: false })
    const next = fn(params({ tab: 'feed' }))
    assert.equal(next.get('tab'), 'forge')
  })

  it('replaceHygiene calls setSearchParams with replace:true', () => {
    const setSearchParams = mock.fn()
    const mutator = (prev) => {
      const next = new URLSearchParams(prev)
      next.delete('cve')
      return next
    }
    replaceHygiene(setSearchParams, mutator)
    assert.equal(setSearchParams.mock.calls.length, 1)
    const [fn, opts] = setSearchParams.mock.calls[0].arguments
    assert.equal(typeof fn, 'function')
    assert.deepEqual(opts, { replace: true })
    const next = fn(params({ tab: 'feed', cve: 'CVE-2024-1' }))
    assert.equal(next.get('cve'), null)
    assert.equal(next.get('tab'), 'feed')
  })

  it('push and replace are distinct history modes', () => {
    const setSearchParams = mock.fn()
    pushContext(setSearchParams, (prev) => prev)
    replaceHygiene(setSearchParams, (prev) => prev)
    assert.equal(setSearchParams.mock.calls[0].arguments[1].replace, false)
    assert.equal(setSearchParams.mock.calls[1].arguments[1].replace, true)
  })
})
