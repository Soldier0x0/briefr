import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  communityRulesEmptyMessage,
  confidenceMatchLabel,
  composeBasisLabel,
  composeBasisTooltip,
  formatEvidenceSummary,
  detectionFramingNote,
  templateFallbackFraming,
} from './detectLabels.js'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

describe('detectLabels', () => {
  it('uses sentence-case confidence labels', () => {
    assert.equal(confidenceMatchLabel('HIGH'), 'High confidence match')
    assert.equal(confidenceMatchLabel('MEDIUM'), 'Medium confidence match')
    assert.equal(confidenceMatchLabel('LOW'), 'Low confidence match')
  })

  it('labels compose_basis for Detect provenance', () => {
    assert.equal(composeBasisLabel('community'), 'Community rules')
    assert.equal(composeBasisLabel('sigmahq_index'), 'SigmaHQ index')
    assert.equal(composeBasisLabel('nuclei_artifacts'), 'Nuclei / artifacts')
    assert.equal(composeBasisLabel('yara'), 'YARA hashes')
    assert.equal(composeBasisLabel('template_fallback'), 'Template fallback')
    assert.equal(composeBasisLabel('none'), 'Template fallback')
    assert.match(composeBasisTooltip('community'), /community/i)
    assert.match(composeBasisTooltip('sigmahq_index'), /SigmaHQ/i)
    assert.match(composeBasisTooltip('template_fallback'), /template/i)
  })

  it('formats evidence_summary for the Detect framing strip', () => {
    assert.equal(formatEvidenceSummary(null), null)
    assert.equal(
      formatEvidenceSummary({
        evidence_summary: {
          primary_source: 'nuclei_artifacts',
          community_count: 0,
          artifact_count: 2,
          nuclei_count: 1,
        },
      }),
      'Primary: Nuclei / artifacts · community 0 · artifacts 2 · nuclei 1',
    )
  })

  it('states honestly when community rules are absent', () => {
    assert.match(
      communityRulesEmptyMessage({ sigmahq_index: { rules_active: 40, synced_at: '2026-07-01' } }),
      /No CVE-exact SigmaHQ/,
    )
    assert.match(
      communityRulesEmptyMessage({ sigmahq_index: { rules_active: 0, synced_at: '' } }),
      /not synced yet/,
    )
    assert.match(
      communityRulesEmptyMessage({ sigmahq_index: { rules_active: 0, synced_at: '2026-07-01' } }),
      /empty/,
    )
    assert.match(communityRulesEmptyMessage({}), /No community Sigma\/Elastic/)
  })

  it('templateFallbackFraming reuses empty/template copy and never claims DRL-1.1', () => {
    const miss = templateFallbackFraming({
      sigmahq_index: { rules_active: 40, synced_at: '2026-07-01' },
    })
    assert.match(miss, /No CVE-exact SigmaHQ/)
    assert.match(miss, /template/i)
    assert.doesNotMatch(miss, /DRL-1\.1/)
    assert.doesNotMatch(miss, /Elastic is DRL/)

    const unsynced = templateFallbackFraming({
      sigmahq_index: { rules_active: 0, synced_at: '' },
    })
    assert.match(unsynced, /not synced yet/)
    assert.doesNotMatch(unsynced, /DRL-1\.1/)

    const generic = templateFallbackFraming({})
    assert.equal(
      generic,
      `${communityRulesEmptyMessage({}).replace(/^\/\/\s*/, '')}. ${composeBasisTooltip('template_fallback')}`,
    )
  })

  it('detectionFramingNote uses compose_basis tooltips for Nuclei/YARA', () => {
    assert.equal(
      detectionFramingNote({
        generated_sigma_meta: { compose_basis: 'nuclei_artifacts' },
      }),
      composeBasisTooltip('nuclei_artifacts'),
    )
    assert.equal(
      detectionFramingNote({ generated_sigma_meta: { compose_basis: 'yara' } }),
      composeBasisTooltip('yara'),
    )
    assert.equal(
      detectionFramingNote({
        generated_sigma_meta: { compose_basis: 'template_fallback' },
      }),
      templateFallbackFraming({ generated_sigma_meta: { compose_basis: 'template_fallback' } }),
    )
    assert.doesNotMatch(
      detectionFramingNote({ generated_sigma_meta: { compose_basis: 'nuclei_artifacts' } }),
      /DRL-1\.1/,
    )
  })
})

describe('DC-3 Detect tab evidence pack', () => {
  it('consumes evidence pack and compose_basis in DetectTab', () => {
    const src = fs.readFileSync(
      path.join(ROOT, 'components/DetailDrawer/DetectTab.jsx'),
      'utf8',
    )
    assert.match(src, /formatEvidenceSummary/)
    assert.match(src, /composeBasisLabel/)
    assert.match(src, /communityRulesEmptyMessage/)
    assert.match(src, /detectionFramingNote/)
    assert.match(src, /hasCommunity &&/)
    assert.match(src, /!hasCommunity &&/)
    assert.match(src, /supplement/)
    assert.match(src, /detection\.evidence/)
    assert.match(src, /compose_basis/)
    assert.match(src, /det-evidence-summary/)
    assert.match(src, /Show YAML/)
    assert.match(src, /det-rule-attribution/)
  })
})