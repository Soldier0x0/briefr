import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  ANALYST_HIDDEN_SECTIONS,
  isAnalystHiddenSection,
  resolveAnalystSection,
  DEFAULT_SECTION,
} from '../pages/security-architecture/constants.js'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const SA_PAGE = path.join(ROOT, 'pages', 'security-architecture', 'SecurityArchitecturePage.jsx')
const OVERVIEW = path.join(ROOT, 'pages', 'security-architecture', 'sections', 'OverviewSection.jsx')

function read(file) {
  return fs.readFileSync(file, 'utf8')
}

describe('PM-4b analyst ARCH cleanup gate', () => {
  it('denylists Security Decisions, Reviews, and Components', () => {
    assert.deepEqual(
      [...ANALYST_HIDDEN_SECTIONS].sort(),
      ['components', 'reviews', 'security_decisions'],
    )
    for (const id of ANALYST_HIDDEN_SECTIONS) {
      assert.equal(isAnalystHiddenSection(id), true)
      assert.equal(resolveAnalystSection(id), DEFAULT_SECTION)
    }
    assert.equal(resolveAnalystSection('risks'), 'risks')
  })

  it('removes corpus footer and ADR/Reviews section mounts from ARCH shell', () => {
    const page = read(SA_PAGE)
    assert.doesNotMatch(page, /sa-nav-meta/)
    assert.doesNotMatch(page, /DecisionsSection/)
    assert.doesNotMatch(page, /ReviewHistorySection/)
    assert.doesNotMatch(page, /security_decisions/)
    assert.match(page, /isAnalystHiddenSection/)
    assert.match(page, /resolveAnalystSection/)
  })

  it('overview stack drills to system architecture instead of Components', () => {
    const overview = read(OVERVIEW)
    assert.match(overview, /onDrill\('system_architecture'\)/)
    assert.doesNotMatch(overview, /onDrill\('components'/)
    assert.match(overview, /isAnalystHiddenSection/)
  })
})
