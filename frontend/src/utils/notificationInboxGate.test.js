import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'url'

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const src = fs.readFileSync(path.join(root, 'components/NotificationBell.jsx'), 'utf8')

describe('NotificationBell inbox gate', () => {
  it('does not mark seen merely by opening', () => {
    assert.doesNotMatch(src, /markNotificationsSeen/)
    assert.doesNotMatch(src, /\/notifications\/seen/)
  })

  it('uses Popover, not a raw absolute panel as the only overlay', () => {
    assert.match(src, /PopoverContent/)
  })

  it('does not label dismiss as Mark read', () => {
    assert.doesNotMatch(src, /Mark read/)
    assert.doesNotMatch(src, /Mark all read/)
    assert.match(src, /Mark all as read/)
    assert.match(src, /Clear all/)
  })

  it('labels the tray Alerts and Cleared, not Inbox or Done', () => {
    assert.match(src, /Alerts/)
    assert.match(src, /Cleared/)
    assert.doesNotMatch(src, /<TabsTrigger value="inbox">Inbox<\/TabsTrigger>/)
    assert.doesNotMatch(src, /<TabsTrigger value="done">Done<\/TabsTrigger>/)
    assert.doesNotMatch(src, /Moved to Done/)
  })

  it('leaves Enter handling to nested interactive controls', () => {
    assert.match(
      src,
      /target\.closest\('button, a, \[role="tab"\], input, select, textarea'\)/,
    )
    assert.match(src, /nestedControl !== notificationRow/)
  })

  it('clears only the loaded notification ids', () => {
    assert.doesNotMatch(src, /dismissAllNotifications/)
    assert.match(src, /const ids = filteredItems\.map\(item => item\.id\)/)
    assert.match(
      src,
      /Promise\.allSettled\(ids\.map\(id => dismissNotification\(id\)\)\)/,
    )
  })
})
