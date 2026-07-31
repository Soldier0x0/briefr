import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { DISPLAY_DEFAULTS, toDisplayPrefs } from './displayPrefsCore.js'

describe('displayPrefsCore uiVariant', () => {
  it('defaults uiVariant to default', () => {
    assert.equal(toDisplayPrefs({}).uiVariant, 'default')
    assert.equal(DISPLAY_DEFAULTS.uiVariant, 'default')
  })

  it('maps api snake_case to uiVariant', () => {
    assert.equal(toDisplayPrefs({ ui_variant: 'pitch' }).uiVariant, 'pitch')
  })

  it('falls back to default for unknown variants', () => {
    assert.equal(toDisplayPrefs({ ui_variant: 'neon' }).uiVariant, 'default')
  })
})
