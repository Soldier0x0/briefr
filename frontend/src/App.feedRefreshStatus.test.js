import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const src = await readFile(new URL('./App.jsx', import.meta.url), 'utf8')

describe('FeedRefreshStatus footer copy', () => {
  it('does not advertise orphaned auto daily cache refresh schedule', () => {
    assert.doesNotMatch(src, /auto daily/)
    assert.doesNotMatch(src, /formatScheduleLabel/)
    assert.doesNotMatch(src, /refreshSchedule/)
  })
})
