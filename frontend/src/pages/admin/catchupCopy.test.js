import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  CATCHUP_DESCRIPTION,
  durationPresets,
  formatCatchupEndsIn,
} from './catchupCopy.js'

describe('catchupCopy', () => {
  it('exposes neutral description', () => {
    assert.equal(
      CATCHUP_DESCRIPTION,
      'Catch-up uses more of this machine’s CPU, disk, and network to clear backlog while still respecting each provider’s rate limits. Interactive use may feel slower until Catch-up ends.',
    )
    assert.match(CATCHUP_DESCRIPTION, /rate limits/i)
    assert.match(CATCHUP_DESCRIPTION, /may feel slower/i)
    assert.doesNotMatch(CATCHUP_DESCRIPTION, /laptop|server|overnight/i)
  })

  it('default preset is 6h', () => {
    assert.equal(durationPresets.find((preset) => preset.default)?.hours, 6)
  })

  it('formats active end time relative to now', () => {
    assert.equal(formatCatchupEndsIn('2026-07-20T16:30:00Z', Date.parse('2026-07-20T15:00:00Z')), '1h 30m')
    assert.equal(formatCatchupEndsIn('2026-07-20T15:04:00Z', Date.parse('2026-07-20T15:00:00Z')), '4m')
    assert.equal(formatCatchupEndsIn(null, Date.parse('2026-07-20T15:00:00Z')), '—')
  })
})
