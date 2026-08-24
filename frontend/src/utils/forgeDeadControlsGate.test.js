import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  clusterMemberInventory,
  clusterOpenTarget,
  openCvesLabel,
} from './campaignClusterOpen.js'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')

describe('Forge / notification dead-control gate', () => {
  it('Campaigns uses member inventory and honest personalization copy', () => {
    const src = fs.readFileSync(path.join(ROOT, 'components/forge/CampaignsView.jsx'), 'utf8')
    assert.match(src, /clusterMemberInventory/)
    assert.match(src, /openCvesLabel/)
    assert.match(src, /personalizationCopy/)
    assert.match(src, /browseGlobalUnpersonalizedLabel/)
    assert.doesNotMatch(src, /ranked for your stack/)
    assert.doesNotMatch(src, /OPEN CVEs/)
    assert.match(
      fs.readFileSync(path.join(ROOT, 'utils/campaignClusterOpen.js'), 'utf8'),
      /cluster\.members\?\.\[0\]/,
    )
  })

  it('clusterOpenTarget prefers stack → pin → members', () => {
    assert.equal(
      clusterOpenTarget({
        members_on_stack: ['CVE-1'],
        watchlisted_members: ['CVE-2'],
        members: ['CVE-3'],
      }),
      'CVE-1',
    )
    assert.equal(
      clusterOpenTarget({
        members_on_stack: [],
        watchlisted_members: ['CVE-2'],
        members: ['CVE-3'],
      }),
      'CVE-2',
    )
    assert.equal(
      clusterOpenTarget({
        members_on_stack: [],
        watchlisted_members: [],
        members: ['CVE-3', 'CVE-4'],
      }),
      'CVE-3',
    )
    assert.equal(clusterOpenTarget({ members: [] }), null)
    assert.deepEqual(
      clusterMemberInventory({
        members_on_stack: ['CVE-1'],
        watchlisted_members: ['CVE-2'],
        members: ['CVE-1', 'CVE-2', 'CVE-3'],
      }),
      ['CVE-1', 'CVE-2', 'CVE-3'],
    )
    assert.equal(openCvesLabel(1), 'Open CVE')
    assert.equal(openCvesLabel(25), 'Open CVEs')
  })

  it('NotificationBell wires IOC entity_type to tab=ioc&ioc= via navigate', () => {
    const src = fs.readFileSync(path.join(ROOT, 'utils/notificationInbox.js'), 'utf8')
    assert.match(src, /entity_type === 'ioc'/)
    assert.match(src, /params\.set\('ioc'/)
    assert.match(src, /params\.set\('tab', 'ioc'\)/)
  })

  it('App deep-links ?ioc= into IOC Lookup prefill', () => {
    const src = fs.readFileSync(path.join(ROOT, 'App.jsx'), 'utf8')
    assert.match(src, /searchParams\.get\('ioc'\)/)
    assert.match(src, /setIocPrefill/)
  })

  it('RateLimitPage API keys link is a real admin route', () => {
    const src = fs.readFileSync(path.join(ROOT, 'pages/admin/RateLimitPage.jsx'), 'utf8')
    assert.match(src, /to="\/admin\?p=apikeys"/)
    assert.doesNotMatch(src, /href="#"[^>]*>API keys/)
  })

  it('Scenarios and Backlog evidence/CVE ids open the drawer when wired', () => {
    const scenarios = fs.readFileSync(path.join(ROOT, 'components/forge/ScenariosView.jsx'), 'utf8')
    const backlog = fs.readFileSync(path.join(ROOT, 'components/forge/BacklogView.jsx'), 'utf8')
    assert.match(scenarios, /openCve\(cve\.cve_id\)/)
    assert.match(backlog, /openCve\(item\.cve_id\)/)
    assert.match(scenarios, /fg-cve-id-link/)
    assert.match(backlog, /fg-cve-id-link/)
  })
})
