import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { formatSectionHeading } from './sectionHeading.js'

describe('sectionHeading', () => {
  it('strips leading slashes from section headings', () => {
    assert.equal(formatSectionHeading('// ACTIVE CAMPAIGNS'), 'ACTIVE CAMPAIGNS')
  })

  it('strips trailing slashes from section headings', () => {
    assert.equal(formatSectionHeading('STACK //'), 'STACK')
  })

  it('keeps already-clean headings unchanged', () => {
    assert.equal(formatSectionHeading('MITRE ATT&CK'), 'MITRE ATT&CK')
  })

  it('handles empty strings', () => {
    assert.equal(formatSectionHeading(''), '')
  })
})
