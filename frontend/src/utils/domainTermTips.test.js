import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  DOMAIN_TERM_TIPS,
  INBOUND_BUCKET_TIPS,
  domainTermTip,
  inboundBucketTip,
} from './domainTermTips.js'

describe('domainTermTips', () => {
  it('covers the jargon-sweep keys with non-empty copy', () => {
    const required = [
      'kev',
      'epss',
      'cvss',
      'poc',
      'tech',
      'topTechniques',
      'whatChanged',
      'topKevVendors',
      'topEpssMovers',
      'watchlistSubtab',
      'isp',
      'asn',
      'otx',
      'vt',
    ]
    for (const key of required) {
      const tip = domainTermTip(key)
      assert.equal(typeof tip, 'string', key)
      assert.ok(tip.length > 20, key)
    }
    assert.equal(Object.keys(DOMAIN_TERM_TIPS).length >= required.length, true)
  })

  it('documents every live inbound rate-limit bucket', () => {
    const live = [
      'ioc',
      'refresh',
      'admin_read',
      'wallboard',
      'login',
      'login_username',
      'auth_refresh',
      'db_explorer',
      'search_token',
    ]
    for (const name of live) {
      assert.ok(inboundBucketTip(name), name)
    }
    assert.equal(Object.keys(INBOUND_BUCKET_TIPS).length, live.length)
  })

  it('returns null for unknown keys', () => {
    assert.equal(domainTermTip('nope'), null)
    assert.equal(inboundBucketTip('nope'), null)
  })
})
