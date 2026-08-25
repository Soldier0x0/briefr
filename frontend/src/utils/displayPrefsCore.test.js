import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { DISPLAY_DEFAULTS, toDisplayPrefs } from './displayPrefsCore.js'
import { DEFAULT_NOTIFICATION_MUTES } from './notificationInbox.js'

describe('displayPrefsCore uiVariant', () => {
  it('defaults uiVariant to pitch (showcase)', () => {
    assert.equal(toDisplayPrefs({}).uiVariant, 'pitch')
    assert.equal(DISPLAY_DEFAULTS.uiVariant, 'pitch')
  })

  it('maps api snake_case to uiVariant', () => {
    assert.equal(toDisplayPrefs({ ui_variant: 'pitch' }).uiVariant, 'pitch')
  })

  it('falls back to pitch for unknown variants', () => {
    assert.equal(toDisplayPrefs({ ui_variant: 'neon' }).uiVariant, 'pitch')
  })
})

describe('displayPrefsCore notificationMutes', () => {
  it('defaults notificationMutes to all categories false', () => {
    assert.deepEqual(toDisplayPrefs({}).notificationMutes, DEFAULT_NOTIFICATION_MUTES)
    assert.deepEqual(DISPLAY_DEFAULTS.notificationMutes, DEFAULT_NOTIFICATION_MUTES)
  })

  it('maps api notification_mutes snake_case', () => {
    const prefs = toDisplayPrefs({
      notification_mutes: { watchlist: true, job_error: true },
    })
    assert.equal(prefs.notificationMutes.watchlist, true)
    assert.equal(prefs.notificationMutes.job_error, true)
    assert.equal(prefs.notificationMutes.ioc_watchlist, false)
  })
})
