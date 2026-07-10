import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  canPauseResume,
  canRunNow,
  nextRunCell,
  pauseResumeAction,
} from './jobActions.js'

describe('jobActions', () => {
  it('canRunNow blocks LOCKED and DISABLED', () => {
    assert.equal(canRunNow('ACTIVE'), true)
    assert.equal(canRunNow('PAUSED'), true)
    assert.equal(canRunNow('LOCKED'), false)
    assert.equal(canRunNow('DISABLED'), false)
  })

  it('canPauseResume only for ACTIVE and PAUSED', () => {
    assert.equal(canPauseResume('ACTIVE'), true)
    assert.equal(canPauseResume('PAUSED'), true)
    assert.equal(canPauseResume('DISABLED'), false)
    assert.equal(canPauseResume('LOCKED'), false)
  })

  it('pauseResumeAction returns null for DISABLED and LOCKED', () => {
    assert.equal(pauseResumeAction('PAUSED'), 'resume')
    assert.equal(pauseResumeAction('ACTIVE'), 'pause')
    assert.equal(pauseResumeAction('DISABLED'), null)
    assert.equal(pauseResumeAction('LOCKED'), null)
  })

  it('nextRunCell shows disabled and paused labels', () => {
    const fmt = v => v || '—'
    assert.equal(nextRunCell('PAUSED', null, fmt), '(paused)')
    assert.equal(nextRunCell('DISABLED', null, fmt), '(disabled)')
    assert.equal(nextRunCell('ACTIVE', '2026-01-01', fmt), '2026-01-01')
  })
})
