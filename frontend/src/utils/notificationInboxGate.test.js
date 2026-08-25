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
    assert.match(src, /Done/)
  })

  it('leaves Enter handling to nested interactive controls', () => {
    assert.match(
      src,
      /target\.closest\('button, a, \[role="tab"\], input, select, textarea'\)/,
    )
    assert.match(src, /nestedControl !== notificationRow/)
  })

  it('moves only the loaded notification ids to Done', () => {
    assert.doesNotMatch(src, /dismissAllNotifications/)
    assert.match(src, /const ids = filteredItems\.map\(item => item\.id\)/)
    assert.match(
      src,
      /Promise\.allSettled\(ids\.map\(id => dismissNotification\(id\)\)\)/,
    )
    assert.match(src, /view === 'inbox' && filteredItems\.length > 0/)
  })
})
