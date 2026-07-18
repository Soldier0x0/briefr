import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { nextLocalStack } from './stackLocalSync.js'

describe('nextLocalStack (STACK caret / spacebar RCA)', () => {
  it('keeps trailing spaces when external value is only a trim of local', () => {
    assert.equal(nextLocalStack('nginx ', 'nginx'), 'nginx ')
    assert.equal(nextLocalStack(' nginx', 'nginx'), ' nginx')
    assert.equal(nextLocalStack('a b ', 'a b'), 'a b ')
  })

  it('accepts real external changes (clear, My Stack load)', () => {
    assert.equal(nextLocalStack('nginx ', ''), '')
    assert.equal(nextLocalStack('nginx', 'python, linux'), 'python, linux')
  })

  it('is a no-op when already equal', () => {
    assert.equal(nextLocalStack('nginx', 'nginx'), 'nginx')
    assert.equal(nextLocalStack('', ''), '')
  })
})
