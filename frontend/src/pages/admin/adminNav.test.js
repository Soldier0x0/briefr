import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { resolveAdminPage, ADMIN_MODE_LABELS } from './constants.js'

describe('resolveAdminPage (E8-2)', () => {
  it('resolves operator nav pages with section', () => {
    const page = resolveAdminPage('scheduler', 'operator')
    assert.equal(page.section, 'CONFIGURATION')
    assert.equal(page.label, 'Scheduler')
    assert.equal(page.pageId, 'scheduler')
  })

  it('resolves analyst nav pages', () => {
    const page = resolveAdminPage('feedhealth', 'analyst')
    assert.equal(page.section, 'INTEL')
    assert.equal(page.label, 'Source status')
  })

  it('falls back for unknown page ids', () => {
    const page = resolveAdminPage('unknown-page', 'operator')
    assert.equal(page.label, 'unknown-page')
    assert.equal(page.section, null)
  })

  it('exposes mode labels for breadcrumbs', () => {
    assert.equal(ADMIN_MODE_LABELS.analyst, 'Analyst view')
    assert.equal(ADMIN_MODE_LABELS.operator, 'Operator view')
  })
})
