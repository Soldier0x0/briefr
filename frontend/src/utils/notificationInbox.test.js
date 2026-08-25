import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  notificationDestination,
  groupNotificationRows,
  notificationTriggerLabel,
} from './notificationInbox.js'

describe('notificationDestination', () => {
  it('opens CVE in feed', () => {
    const d = notificationDestination({ entity_type: 'cve', entity_id: 'CVE-1' })
    assert.equal(d.pathname, '/')
    assert.match(d.search, /tab=feed/)
    assert.match(d.search, /cve=CVE-1/)
    assert.equal(d.label, 'Open CVE')
  })
  it('returns null for unknown types', () => {
    assert.equal(notificationDestination({ entity_type: 'nope', entity_id: 'x' }), null)
  })
})

describe('groupNotificationRows', () => {
  it('collapses consecutive same entity', () => {
    const groups = groupNotificationRows([
      { id: 1, category: 'watchlist', entity_type: 'cve', entity_id: 'CVE-1', title: 'b' },
      { id: 2, category: 'watchlist', entity_type: 'cve', entity_id: 'CVE-1', title: 'a' },
      { id: 3, category: 'job_error', entity_type: 'job', entity_id: 'nvd', title: 'j' },
    ])
    assert.equal(groups.length, 2)
    assert.equal(groups[0].extras.length, 1)
  })
})

describe('notificationTriggerLabel', () => {
  it('includes unread count', () => {
    assert.equal(notificationTriggerLabel(3), 'Notifications, 3 unread')
    assert.equal(notificationTriggerLabel(0), 'Notifications, none unread')
  })
})
