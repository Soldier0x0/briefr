import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  LAYOUT_STORAGE_PREFIX,
  layoutPrefsKey,
  loadLayoutPrefs,
  saveLayoutPrefs,
} from './gridLayoutPrefs.js'

describe('gridLayoutPrefs', () => {
  it('uses layoutGroupId when provided for shared wrap/center prefs', () => {
    assert.equal(layoutPrefsKey('sa-mitre-initial-access', 'sa-mitre'), 'sa-mitre')
    assert.equal(layoutPrefsKey('sa-threat-scenarios', null), 'sa-threat-scenarios')
  })

  it('loadLayoutPrefs returns wrap/center defaults when storage is empty', () => {
    const key = `test-${Date.now()}-empty`
    assert.deepEqual(loadLayoutPrefs(key), { wrap: false, center: false })
  })

  it('saveLayoutPrefs round-trips wrap and center', () => {
    const key = `test-${Date.now()}-roundtrip`
    saveLayoutPrefs(key, { wrap: true, center: true })
    assert.deepEqual(loadLayoutPrefs(key), { wrap: true, center: true })
    saveLayoutPrefs(key, { wrap: false, center: false })
    assert.deepEqual(loadLayoutPrefs(key), { wrap: false, center: false })
  })
})
