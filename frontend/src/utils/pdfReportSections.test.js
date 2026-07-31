import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  formatCapecSection,
  formatDetectionOverview,
  formatRelatedSection,
  formatTriageSnapshot,
  pickCommunitySigmaYaml,
  pickHuntStarterYaml,
} from './pdfReportSections.js'

describe('pdfReportSections', () => {
  it('formats triage snapshot with OP, threat, SSVC, and KEV due', () => {
    const body = formatTriageSnapshot(
      { is_kev: true, kev_due_date: '2026-08-15' },
      {
        operational_priority: { band: 'P1', provisional: false, escalated_by_correlation: false },
        threat: { score: 88.2, band: 'CRITICAL' },
        momentumScore: 0.8,
        ssvc: { outcome: 'Act', path: 'active/automatable' },
        environment: { tier: 'LIKELY', evidence_label: 'Apache in stack' },
      },
    )
    assert.match(body, /Operational Priority: P1/)
    assert.match(body, /Threat Score: 88\.2/)
    assert.match(body, /Rising momentum/)
    assert.match(body, /CISA SSVC: Act/)
    assert.match(body, /KEV remediation due:/)
    assert.match(body, /Environment relevance:/)
  })

  it('formats CAPEC ids with MITRE links', () => {
    const body = formatCapecSection({ capec_ids: ['CAPEC-66', '88'] })
    assert.match(body, /CAPEC-66: https:\/\/capec\.mitre\.org/)
    assert.match(body, /CAPEC-88:/)
  })

  it('prefers community sigma YAML over hunt starter', () => {
    const detection = {
      sigma_rules: [{ content: 'title: community\nstatus: test' }],
      generated_sigma: 'title: hunt\nstatus: experimental',
    }
    assert.equal(pickCommunitySigmaYaml(detection), 'title: community\nstatus: test')
    assert.equal(pickHuntStarterYaml(detection), 'title: hunt\nstatus: experimental')
  })

  it('lists detection assets but not generic SIEM queries', () => {
    const body = formatDetectionOverview({
      sigma_rules: [{ title: 'Rule A', match_basis: 'cve_exact' }],
      siem_queries: {
        elastic_kql: { query: 'process.name: foo' },
        log_patterns: ['Watch auth logs for exploit attempts'],
      },
      evidence: { observables: { nuclei_urls: ['https://github.com/projectdiscovery/nuclei-templates'] } },
    })
    assert.match(body, /Community Sigma rules/)
    assert.match(body, /Rule A/)
    assert.match(body, /Log patterns/)
    assert.doesNotMatch(body, /process\.name/)
  })

  it('formats related CVEs and news', () => {
    const body = formatRelatedSection(
      [{ cve_id: 'CVE-2024-1', severity: 'HIGH', cvss_score: 8.1 }],
      [{ source: 'Krebs', title: 'Major breach' }],
      'embeddings',
    )
    assert.match(body, /Similar description/)
    assert.match(body, /CVE-2024-1/)
    assert.match(body, /Krebs: Major breach/)
  })
})
