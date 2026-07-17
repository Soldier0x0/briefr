import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  APP_TABS,
  resolveAppTab,
  buildAppTabSearchParams,
  buildAdminPageSearchParams,
  ADMIN_PAGE_SCOPED_PARAMS,
} from './shellUrlState.js'

function params(obj = {}) {
  return new URLSearchParams(obj)
}

describe('resolveAppTab', () => {
  it('reads tab= when valid', () => {
    assert.equal(resolveAppTab(params({ tab: 'feed' })), 'feed')
    assert.equal(resolveAppTab(params({ tab: 'ioc' })), 'ioc')
    assert.equal(resolveAppTab(params({ tab: 'atlas' })), 'atlas')
    assert.equal(resolveAppTab(params({ tab: 'forge' })), 'forge')
    assert.equal(resolveAppTab(params({ tab: 'brief' })), 'brief')
  })

  it('falls back to forge when legacy view= is present without tab=', () => {
    assert.equal(resolveAppTab(params({ view: 'coverage', technique: 'T1592' })), 'forge')
  })

  it('defaults to brief when empty or unknown', () => {
    assert.equal(resolveAppTab(params()), 'brief')
    assert.equal(resolveAppTab(params({ tab: 'nope' })), 'brief')
  })

  it('prefers explicit tab= over legacy view=', () => {
    assert.equal(resolveAppTab(params({ tab: 'feed', view: 'coverage' })), 'feed')
  })
})

describe('buildAppTabSearchParams', () => {
  it('always sets tab= so BRIEF/FEED/IOC are visible in the URL', () => {
    const next = buildAppTabSearchParams(params(), 'feed')
    assert.equal(next.get('tab'), 'feed')
    assert.deepEqual([...APP_TABS].sort(), ['atlas', 'brief', 'feed', 'forge', 'ioc'])
  })

  it('clears Forge params when leaving forge', () => {
    const prev = params({
      tab: 'forge',
      view: 'coverage',
      technique: 'T1592',
      pack: '1',
    })
    const next = buildAppTabSearchParams(prev, 'brief')
    assert.equal(next.get('tab'), 'brief')
    assert.equal(next.get('view'), null)
    assert.equal(next.get('technique'), null)
    assert.equal(next.get('pack'), null)
  })

  it('keeps Forge params when selecting forge and ensures view=', () => {
    const next = buildAppTabSearchParams(params({ tab: 'brief' }), 'forge')
    assert.equal(next.get('tab'), 'forge')
    assert.equal(next.get('view'), 'coverage')
  })

  it('preserves technique when already on forge with view=', () => {
    const prev = params({ tab: 'forge', view: 'backlog', technique: 'T1059' })
    const next = buildAppTabSearchParams(prev, 'forge')
    assert.equal(next.get('view'), 'backlog')
    assert.equal(next.get('technique'), 'T1059')
  })
})

describe('buildAdminPageSearchParams', () => {
  it('always sets p= so sidebar navigation is visible in the URL', () => {
    const next = buildAdminPageSearchParams(params({ p: 'scheduler', job_id: 'x' }), 'overview')
    assert.equal(next.get('p'), 'overview')
    assert.equal(next.get('job_id'), null)
  })

  it('drops every page-scoped deep-link key when changing pages', () => {
    const prev = params({
      p: 'securityposture',
      section: 'attack_surface',
      node: 'n1',
      window: '7d',
      level: 'ERROR',
      source: 'nvd',
    })
    const next = buildAdminPageSearchParams(prev, 'feedhealth')
    assert.equal(next.get('p'), 'feedhealth')
    for (const key of ADMIN_PAGE_SCOPED_PARAMS) {
      assert.equal(next.get(key), null, key)
    }
  })

  it('returns prev unchanged when p already matches (keep in-page filters)', () => {
    const prev = params({ p: 'ingestlog', job_id: 'sync_nvd', level: 'ERROR' })
    const next = buildAdminPageSearchParams(prev, 'ingestlog')
    assert.equal(next, prev)
  })
})
