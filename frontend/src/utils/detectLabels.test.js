import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  confidenceMatchLabel,
  composeBasisLabel,
  composeBasisTooltip,
  formatEvidenceSummary,
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
    assert.equal(composeBasisLabel('nuclei_artifacts'), 'Nuclei / artifacts')
    assert.equal(composeBasisLabel('yara'), 'YARA hashes')
    assert.equal(composeBasisLabel('template_fallback'), 'Template fallback')
    assert.equal(composeBasisLabel('none'), 'Template fallback')
    assert.match(composeBasisTooltip('community'), /community/i)
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
})

describe('DC-3 Detect tab evidence pack', () => {
  it('consumes evidence pack and compose_basis in DetectTab', () => {
    const src = fs.readFileSync(
      path.join(ROOT, 'components/DetailDrawer/DetectTab.jsx'),
      'utf8',
    )
    assert.match(src, /formatEvidenceSummary/)
    assert.match(src, /composeBasisLabel/)
    assert.match(src, /detection\.evidence/)
    assert.match(src, /compose_basis/)
    assert.match(src, /det-evidence-summary/)
  })
})