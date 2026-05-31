import LegalPage from './LegalPage.jsx'

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms of Service"
      subtitle="Effective June 2026 — projectjupiter.in"
    >
      <h2 className="legal-section-heading">1. What BRIEFR is</h2>
      <p className="legal-p">
        BRIEFR is a free, publicly accessible CVE intelligence aggregation tool.
        It fetches data from public government and open-source sources and
        presents it in a searchable interface. It is provided as-is, at no cost,
        for informational and research purposes.
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
        <li>Automated scraping exceeding 120 requests per minute</li>
        <li>Attempting to tamper with or disrupt the service</li>
        <li>Using IOC Lookup to investigate individuals without legal authority</li>
        <li>Reselling BRIEFR data as a commercial product without attribution</li>
      </ul>

      <h2 className="legal-section-heading">4. Data accuracy</h2>
      <p className="legal-p">
        BRIEFR aggregates from NVD, CISA, EPSS, and OSV.dev. We do not guarantee
        accuracy or timeliness. Do not make critical security decisions based
        solely on BRIEFR without cross-referencing primary sources.
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

      <h2 className="legal-section-heading">8. Contact</h2>
      <p className="legal-p">
        Open an issue on the BRIEFR GitHub repository for any questions about
        these terms.
      </p>
    </LegalPage>
  )
}
