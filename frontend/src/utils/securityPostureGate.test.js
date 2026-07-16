import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const CONSTANTS = path.join(ROOT, 'pages', 'admin', 'constants.js')
const ADMIN_PAGE = path.join(ROOT, 'pages', 'admin', 'AdminPage.jsx')
const POSTURE_PAGE = path.join(ROOT, 'pages', 'admin', 'SecurityPosturePage.jsx')
const REQUIRE_ADMIN = path.join(ROOT, 'components', 'RequireAdmin.jsx')

function read(file) {
  return fs.readFileSync(file, 'utf8')
}

describe('PM-4a Security posture gate', () => {
  it('registers securityposture in admin nav and page map', () => {
    const constants = read(CONSTANTS)
    assert.match(constants, /id:\s*'securityposture'/)
    assert.match(constants, /SECURITY POSTURE/)
    const adminPage = read(ADMIN_PAGE)
    assert.match(adminPage, /securityposture/)
    assert.match(adminPage, /SecurityPosturePage/)
  })

  it('embeds the five posture ARCH sections', () => {
    const posture = read(POSTURE_PAGE)
    for (const id of [
      'overview',
      'system_architecture',
      'trust_boundaries',
      'attack_surface',
      'risks',
    ]) {
      assert.match(posture, new RegExp(id))
    }
    assert.match(posture, /OverviewSection/)
    assert.match(posture, /ArchitectureGraphSection/)
    assert.match(posture, /TrustBoundariesSection/)
    assert.match(posture, /AttackSurfaceSection/)
    assert.match(posture, /RiskRegisterSection/)
  })

  it('allows analyst role to open securityposture under Admin', () => {
    const requireAdmin = read(REQUIRE_ADMIN)
    assert.match(requireAdmin, /ANALYST_ADMIN_PAGES[\s\S]*securityposture/)
  })
})
