import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

describe('Toast module', () => {
  it('exports ToastProvider and useToast', async () => {
    const mod = await import('../components/Toast.jsx')
    assert.equal(typeof mod.ToastProvider, 'function')
    assert.equal(typeof mod.useToast, 'function')
  })
})
