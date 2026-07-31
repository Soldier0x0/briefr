import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  collectOfficialSigmaRulesForPdf,
  formatCapecSection,
  formatDetectionOverview,
  formatRelatedSection,
  formatSigmaAttribution,
  formatTriageSnapshot,
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

  it('collects official SigmaHQ rules with attribution and ranks CVE-exact first', () => {
    const detection = {
      sigma_rules: [
        {
          title: 'Technique rule',
          content: 'title: technique',
          source: 'SigmaHQ',
          match_basis: 'technique_related',
        },
        {
          title: 'CVE rule',
          content: 'title: cve',
          source: 'SigmaHQ',
          match_basis: 'cve_exact',
          attribution: 'SigmaHQ · Florian Roth',
          html_url: 'https://github.com/SigmaHQ/sigma/blob/master/rule.yml',
        },
      ],
      generated_sigma: 'title: briefr-generated',
    }
    const rules = collectOfficialSigmaRulesForPdf(detection)
    assert.equal(rules.length, 2)
    assert.equal(rules[0].title, 'CVE rule')
    assert.match(rules[0].attribution, /SigmaHQ/)
    assert.match(formatSigmaAttribution(rules[0]), /Source: https:\/\/github.com/)
    assert.doesNotMatch(rules.map(r => r.content).join('\n'), /briefr-generated/)
  })

  it('lists only official detection sources and omits BRIEFR templates', () => {
    const body = formatDetectionOverview({
      sigma_rules: [{
        title: 'Rule A',
        content: 'title: official',
        source: 'SigmaHQ',
        match_basis: 'cve_exact',
        attribution: 'SigmaHQ · Author',
        license: 'DRL-1.1',
      }],
      elastic_rules: [{ name: 'Elastic rule', html_url: 'https://github.com/elastic/detection-rules' }],
      generated_sigma: 'title: hunt starter',
      yara_rules: [{ yara: 'rule generated {}' }],
      siem_queries: {
        elastic_kql: { query: 'process.name: foo' },
        log_patterns: ['Watch auth logs'],
      },
      evidence: { observables: { nuclei_urls: ['https://github.com/projectdiscovery/nuclei-templates'] } },
    })
    assert.match(body, /Official SigmaHQ rules/)
    assert.match(body, /SigmaHQ · Author/)
    assert.match(body, /License: DRL-1.1/)
    assert.match(body, /Official Elastic detection rules/)
    assert.doesNotMatch(body, /hunt starter/i)
    assert.doesNotMatch(body, /YARA/)
    assert.doesNotMatch(body, /Log patterns/)
    assert.doesNotMatch(body, /Nuclei/)
    assert.doesNotMatch(body, /process\.name/)
  })

  it('states when no official rules matched', () => {
    const body = formatDetectionOverview({
      generated_sigma: 'title: only briefr',
      siem_queries: { log_patterns: ['noise'] },
    })
    assert.match(body, /No official community detection rules/)
    assert.doesNotMatch(body, /BRIEFR-generated/)
    assert.doesNotMatch(body, /omitted/)
  })

  it('always includes license and author credit in sigma attribution', () => {
    const withAuthor = formatSigmaAttribution({
      author: 'Florian Roth',
      license: 'DRL-1.1',
      html_url: 'https://github.com/SigmaHQ/sigma/blob/master/rule.yml',
    })
    assert.match(withAuthor, /SigmaHQ · Florian Roth/)
    assert.match(withAuthor, /License: DRL-1.1/)

    const withoutAuthor = formatSigmaAttribution({ html_url: 'https://github.com/SigmaHQ/sigma' })
    assert.match(withoutAuthor, /author credit required/)
    assert.match(withoutAuthor, /License: DRL-1.1/)
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
