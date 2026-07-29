import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { sanitizePdfText, pdfContentWidth } from './pdfText.js'

describe('sanitizePdfText', () => {
  it('collapses irregular unicode and ascii whitespace', () => {
    const input = 'public\u00a0proof\u2009of\u2002concept'
    assert.equal(sanitizePdfText(input), 'public proof of concept')
  })

  it('strips simple markdown emphasis', () => {
    assert.equal(
      sanitizePdfText('**Critical** flaw in `auth`'),
      'Critical flaw in auth',
    )
  })

  it('preserves paragraph breaks', () => {
    assert.equal(sanitizePdfText('line one\n\nline two'), 'line one\n\nline two')
  })
})

describe('pdfContentWidth', () => {
  it('subtracts margins and inner padding', () => {
    assert.equal(pdfContentWidth(210, 15, 10), 170)
  })
})
