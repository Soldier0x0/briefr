import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const HEADER = path.join(ROOT, 'components', 'Header.jsx')
const APP = path.join(ROOT, 'App.jsx')
const POSTURE = path.join(ROOT, 'pages', 'admin', 'SecurityPosturePage.jsx')

function read(file) {
  return fs.readFileSync(file, 'utf8')
}

describe('PM-4c remove ARCH tab gate', () => {
  it('removes ARCH from desktop and mobile header nav', () => {
    const header = read(HEADER)
    assert.doesNotMatch(header, /to="\/security-architecture"/)
    assert.doesNotMatch(header, />\s*ARCH\s*</)
  })

  it('redirects /security-architecture to Admin security posture', () => {
    const app = read(APP)
    assert.match(app, /SecurityArchitectureRedirect/)
    assert.match(app, /next\.set\('p',\s*'securityposture'\)/)
    assert.doesNotMatch(app, /lazyWithReload\(\(\) => import\('\.\/pages\/security-architecture\/SecurityArchitecturePage/)
  })

  it('Security posture no longer navigates to the stand-alone ARCH route', () => {
    const posture = read(POSTURE)
    assert.doesNotMatch(posture, /window\.location\.assign\(`\/security-architecture/)
    assert.doesNotMatch(posture, /until the ARCH tab is retired/)
    assert.doesNotMatch(posture, /<Link to="\/security-architecture"/)
  })
})
