import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  browseGlobalUnpersonalizedLabel,
  campaignsEmptyGuidance,
  campaignsPanelHint,
  forgeHeroSub,
  hasPersonalizationContext,
  unpersonalizedBadgeLabel,
  wallboardCoverageEmpty,
} from './personalizationCopy.js'

describe('personalizationCopy', () => {
  it('detects personalization from stack terms or pins', () => {
    assert.equal(hasPersonalizationContext({}), false)
    assert.equal(hasPersonalizationContext({ stackTerms: '' }), false)
    assert.equal(hasPersonalizationContext({ stackTerms: '   ' }), false)
    assert.equal(hasPersonalizationContext({ pinCount: 0 }), false)
    assert.equal(hasPersonalizationContext({ stackTerms: 'log4j' }), true)
    assert.equal(hasPersonalizationContext({ stackTerms: ['apache', 'nginx'] }), true)
    assert.equal(hasPersonalizationContext({ pinCount: 2 }), true)
    assert.equal(hasPersonalizationContext({ stackTerms: '', pinCount: 1 }), true)
  })

  it('never claims ranked-for-stack when unpersonalized', () => {
    const plain = campaignsPanelHint({ hasStack: false, hasPins: false })
    assert.doesNotMatch(plain, /ranked for your stack/i)
    assert.match(plain, /not personalized/i)

    const stackOnly = campaignsPanelHint({ hasStack: true, hasPins: false })
    assert.match(stackOnly, /your stack/i)
    assert.doesNotMatch(stackOnly, /ranked for your stack/i)

    const pinsOnly = campaignsPanelHint({ hasStack: false, hasPins: true })
    assert.doesNotMatch(pinsOnly, /filtered by your stack/i)
    assert.match(pinsOnly, /pinned/i)
  })

  it('offers browse-global guidance copy', () => {
    assert.match(campaignsEmptyGuidance(), /unpersonalized/i)
    assert.equal(browseGlobalUnpersonalizedLabel(), 'Browse global (unpersonalized)')
    assert.equal(unpersonalizedBadgeLabel(), 'UNPERSONALIZED')
  })

  it('Forge hero avoids stack claim without personalization', () => {
    const plain = forgeHeroSub({ personalized: false })
    assert.doesNotMatch(plain, /for your stack/)
    assert.match(plain, /Load My Stack/)
    assert.match(forgeHeroSub({ personalized: true }), /for your stack/)
  })

  it('Wallboard coverage empty distinguishes global vs stack', () => {
    assert.equal(
      wallboardCoverageEmpty({ stackConfigured: false }),
      'No coverage gaps in the global technique map',
    )
    assert.equal(
      wallboardCoverageEmpty({ stackConfigured: true }),
      'No coverage gaps on your stack',
    )
  })
})
