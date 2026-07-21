import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { formatIntelLabel, formatIntelLabelText, INTEL_PART_TOOLTIP } from './formatIntelLabel.js'

describe('formatIntelLabel', () => {
  it('humanizes Known_Cve underscore labels', () => {
    const result = formatIntelLabel('Known_Cve')
    assert.equal(result.title, 'Known Cve')
    assert.equal(result.part, null)
    assert.equal(result.raw, 'Known_Cve')
  })

  it('collapses multiple underscores and spaces', () => {
    assert.equal(formatIntelLabel('Foo__Bar___Baz').title, 'Foo Bar Baz')
    assert.equal(formatIntelLabel('  Spaced___Name  ').title, 'Spaced Name')
  })

  it('returns empty title for null/undefined/blank', () => {
    assert.deepEqual(formatIntelLabel(null), { title: '', part: null, raw: '' })
    assert.deepEqual(formatIntelLabel(undefined), { title: '', part: null, raw: '' })
    assert.deepEqual(formatIntelLabel(''), { title: '', part: null, raw: '' })
    assert.deepEqual(formatIntelLabel('   '), { title: '', part: null, raw: '' })
    assert.equal(formatIntelLabelText(null), '')
  })

  it('leaves already-human spaced labels mostly intact', () => {
    const result = formatIntelLabel('LockBit 3.0 Campaign')
    assert.equal(result.title, 'LockBit 3.0 Campaign')
    assert.equal(result.raw, 'LockBit 3.0 Campaign')
  })

  it('collapses whitespace on already-human labels without changing casing', () => {
    assert.equal(formatIntelLabel('  Foo   Bar  ').title, 'Foo Bar')
  })

  it('parses author Part N/M without fabricating missing parts', () => {
    const result = formatIntelLabel('Known_Cve | Part 1/2')
    assert.equal(result.title, 'Known Cve')
    assert.deepEqual(result.part, { n: 1, m: 2 })
    assert.equal(result.raw, 'Known_Cve | Part 1/2')
    assert.ok(INTEL_PART_TOOLTIP.includes('OTX author-assigned'))
  })

  it('keeps trailing period titles on display (matching is Task 6)', () => {
    const result = formatIntelLabel('Apache_Struts_RCE.')
    assert.equal(result.title, 'Apache Struts Rce.')
    assert.equal(result.raw, 'Apache_Struts_RCE.')
  })

  it('does not invent Part when suffix is absent', () => {
    assert.equal(formatIntelLabel('Known_Cve').part, null)
  })
})
