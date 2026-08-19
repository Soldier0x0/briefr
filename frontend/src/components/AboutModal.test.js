import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

describe('About / Privacy / Terms stay aligned with product truth', () => {
  it('About lists SigmaHQ, requires sign-in, and drops the no-account claim', () => {
    const src = fs.readFileSync(
      path.join(ROOT, 'components/AboutModal.jsx'),
      'utf8',
    )
    assert.match(src, /SigmaHQ/)
    assert.match(src, /sign-in/i)
    assert.doesNotMatch(src, /No account required/)
    assert.match(src, /DRL-1\.1/)
    assert.match(src, /Community detection rules/)
  })

  it('About modal CSS is landscape (wider, capped height)', () => {
    const css = fs.readFileSync(
      path.join(ROOT, 'components/AboutModal.css'),
      'utf8',
    )
    assert.match(css, /max-width:\s*var\(--modal-about-max-width\)/)
    assert.match(css, /max-height:\s*var\(--modal-about-max-height\)/)
    assert.match(css, /grid-template-columns:\s*1fr 1fr/)
    const mobileBlock = css.split('@media (max-width: 720px)')[1] || ''
    assert.match(mobileBlock, /max-height:\s*var\(--modal-about-max-height-narrow\)/)
    const tokens = fs.readFileSync(
      path.join(ROOT, 'styles/tokens.css'),
      'utf8',
    )
    assert.match(tokens, /--modal-about-max-height-narrow:\s*88vh/)
    assert.match(tokens, /--modal-about-max-width:\s*1080px/)
  })

  it('Privacy documents SigmaHQ sync and current feed cadences', () => {
    const src = fs.readFileSync(
      path.join(ROOT, 'pages/PrivacyPage.jsx'),
      'utf8',
    )
    assert.match(src, /Effective July 2026/)
    assert.match(src, /SigmaHQ/)
    assert.match(src, /default hourly/)
    assert.match(src, /15 minutes/)
    assert.match(src, /6 hours/)
    assert.match(src, /DRL-1\.1/)
  })

  it('Terms cover login-gated hosting and community rule honesty', () => {
    const src = fs.readFileSync(
      path.join(ROOT, 'pages/TermsPage.jsx'),
      'utf8',
    )
    assert.match(src, /Effective July 2026/)
    assert.match(src, /sign-in/)
    assert.match(src, /SigmaHQ/)
    assert.match(src, /experimental hunt starters/)
    assert.match(src, /DRL-1\.1/)
  })
})
