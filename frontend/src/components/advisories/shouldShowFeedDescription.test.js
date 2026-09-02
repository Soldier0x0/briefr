import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { shouldShowFeedDescription } from './shouldShowFeedDescription.js'

const SHARED = path.join(path.dirname(fileURLToPath(import.meta.url)), 'shared.jsx')

describe('shouldShowFeedDescription', () => {
  it('is re-exported from shared.jsx for FeedCard', () => {
    const src = fs.readFileSync(SHARED, 'utf8')
    assert.match(src, /export \{ shouldShowFeedDescription \}/)
    assert.match(src, /shouldShowFeedDescription\(card\.title, card\.description\)/)
  })

  it('hides empty and title-cloned subtitles', () => {
    assert.equal(shouldShowFeedDescription('CISA adds VPN flaw', ''), false)
    assert.equal(shouldShowFeedDescription('CISA adds VPN flaw', '   '), false)
    assert.equal(
      shouldShowFeedDescription('CISA adds VPN flaw', 'CISA adds VPN flaw'),
      false,
    )
  })

  it('shows a distinct description', () => {
    assert.equal(
      shouldShowFeedDescription('CISA adds VPN flaw', 'Agency added the CVE to KEV.'),
      true,
    )
  })
})
