import LegalPage from './LegalPage.jsx'

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms of Use"
      subtitle="Effective July 2026 — projectjupiter.in"
    >
      <h2 className="legal-section-heading">1. What BRIEFR is</h2>
      <p className="legal-p">
        BRIEFR is a self-hosted CVE intelligence and detection-engineering
        platform. The hosted instance at projectjupiter.in requires operator
        or analyst sign-in. It aggregates vulnerability and threat data from
        public government and open-source sources and presents it for triage,
        investigation, and hunt-pack workflows. It is provided as-is for
        informational and research purposes. Commercial use of the software
        is governed by Section 8 (License).
      </p>

      <h2 className="legal-section-heading">2. Permitted use</h2>
      <ul className="legal-ul">
        <li>Security research and vulnerability analysis</li>
        <li>Understanding your organisation's CVE exposure</li>
        <li>Educational use and CTF preparation</li>
        <li>Integration into internal security workflows via the API</li>
      </ul>

      <h2 className="legal-section-heading">3. Prohibited use</h2>
      <ul className="legal-ul">
        <li>Exploiting vulnerabilities in systems you do not own or have no authorisation to test</li>
        <li>Automated scraping or abuse of rate-limited endpoints (IOC lookup: 30 requests/minute, refresh: 10/minute, wallboard: 60/minute)</li>
        <li>Attempting to tamper with or disrupt the service</li>
        <li>Using IOC Lookup to investigate individuals without legal authority</li>
        <li>Reselling BRIEFR data as a commercial product without attribution</li>
        <li>Removing or misrepresenting SigmaHQ / third-party rule attribution or license notices (including DRL-1.1)</li>
      </ul>

      <h2 className="legal-section-heading">4. Data accuracy</h2>
      <p className="legal-p">
        BRIEFR aggregates from sources including NVD, CISA KEV, FIRST EPSS,
        OSV.dev, MITRE ATT&amp;CK/ATLAS, AlienVault OTX, CIRCL, Sploitus, and
        community detection content such as SigmaHQ (local index) and Elastic
        detection-rules search. We do not guarantee accuracy or timeliness.
        Community Sigma rules are third-party content under their own licenses
        (typically DRL-1.1 for SigmaHQ); an empty Detect community section
        means no CVE-exact match was found — not that a rule does not exist
        elsewhere. Do not make critical security decisions based solely on
        BRIEFR without cross-referencing primary sources. BRIEFR-generated
        Sigma templates are experimental hunt starters, not production-ready
        detections.
      </p>

      <h2 className="legal-section-heading">5. Disclaimer</h2>
      <p className="legal-p">
        BRIEFR is provided "as-is" without warranty of any kind, express or
        implied. Use at your own risk.
      </p>

      <h2 className="legal-section-heading">6. Limitation of liability</h2>
      <p className="legal-p">
        The BRIEFR maintainers are not liable for any indirect, incidental,
        special, or consequential damages arising from your use of or reliance on
        BRIEFR data.
      </p>

      <h2 className="legal-section-heading">7. Governing law</h2>
      <p className="legal-p">
        These terms are governed by the laws of India. Jurisdiction: Andhra
        Pradesh, India.
      </p>

      <h2 className="legal-section-heading">8. License</h2>
      <p className="legal-p">
        The BRIEFR source code is licensed under the Business Source License
        1.1 (BSL). Copyright &copy; 2026 Sai Harsha Vardhan. Self-hosting and
        use of the source code is free for personal, non-commercial purposes.
        Any use by or on behalf of a for-profit organisation or business
        ("commercial use") requires a one-time, lifetime commercial license —
        contact harsha@projectjupiter.in to obtain one. A commercial license
        grants only the right to use BRIEFR commercially, for life, in
        exchange for a single one-time payment — it is not a support or
        maintenance contract, and does not entitle the licensee to future
        updates, patches, or fixes; a commercial licensee may self-maintain
        their own fork or adopt whatever updates the operator chooses to
        publish, at the operator's discretion. Individuals using BRIEFR for
        free under the personal license may optionally support development
        via Buy Me a Coffee (one-time or monthly) — this is never required,
        and confers no additional rights, support, or update guarantee beyond
        what the free personal license already provides. Self-hosted instances, whether
        under the free personal license or a paid commercial license, are run
        entirely at the operator's own risk: no maintenance, support,
        updates, or uptime guarantee is provided to anyone (see Section 5,
        Disclaimer, which applies equally to self-hosted instances). The
        operator of a
        self-hosted instance is solely responsible for that instance's data
        handling and legal compliance — BRIEFR's Privacy Policy describes only
        the hosted instance at projectjupiter.in. Four years after first
        publication under this BSL, the license converts to the Apache
        License 2.0.
      </p>

      <h2 className="legal-section-heading">9. Contact</h2>
      <p className="legal-p">
        For questions about these terms, including commercial licensing,
        contact Sai Harsha Vardhan (Grievance Officer) at
        harsha@projectjupiter.in.
      </p>
    </LegalPage>
  )
}
