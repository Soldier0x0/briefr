import LegalPage from './LegalPage.jsx'

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      subtitle="Effective June 2026 — projectjupiter.in"
    >
      <h2 className="legal-section-heading">1. What we do not collect</h2>
      <ul className="legal-ul">
        <li>No cookies of any kind</li>
        <li>No analytics (no Google Analytics, no Plausible)</li>
        <li>No user accounts or personal information</li>
        <li>No IP addresses at application layer</li>
        <li>No browser fingerprinting or tracking</li>
        <li>No data sold or shared with third parties</li>
      </ul>

      <h2 className="legal-section-heading">2. What we do collect</h2>

      <h3 className="legal-sub-heading">IOC lookup cache</h3>
      <p className="legal-p">
        When you use IOC Lookup, your submitted IP address, file hash, or domain
        is sent to VirusTotal and AbuseIPDB (third-party services). The result is
        cached locally for 6 hours to reduce API calls. This cache stores only
        the IOC value and the enrichment result — not associated with any user or
        session. Cache entries are automatically deleted after 6 hours.
      </p>

      <h3 className="legal-sub-heading">Server logs</h3>
      <p className="legal-p">
        Nginx logs contain: HTTP method, path, status code, response size. They
        do NOT contain IP addresses, User-Agent strings, or query parameters.
        Logs are retained for 7 days, then deleted.
      </p>

      <h2 className="legal-section-heading">3. localStorage (browser only)</h2>
      <p className="legal-p">
        Your tech stack input is saved to your browser's localStorage under the
        key <code>vektor_stack</code>. This data never leaves your browser and is
        never transmitted to our server. You can clear it at any time in your
        browser settings.
      </p>

      <h2 className="legal-section-heading">4. Third-party services</h2>
      <ul className="legal-ul">
        <li>NVD/NIST — CVE data — server-side, once daily</li>
        <li>CISA — exploited vuln list — server-side, once daily</li>
        <li>FIRST.org — EPSS scores — server-side, once daily</li>
        <li>OSV.dev — open source vulns — server-side, once daily</li>
        <li>VirusTotal — IOC enrichment — only when you use IOC Lookup</li>
        <li>AbuseIPDB — IP reputation — only when you use IOC Lookup</li>
        <li>Google Fonts — typography — every page load from your browser</li>
      </ul>

      <h2 className="legal-section-heading">5. Your rights</h2>
      <p className="legal-p">
        No personal data is stored, so most GDPR and DPDP rights do not apply in
        the traditional sense. You can clear localStorage at any time. IOC cache
        entries auto-purge after 6 hours. For any privacy questions, contact us
        via GitHub.
      </p>

      <h2 className="legal-section-heading">6. Children</h2>
      <p className="legal-p">
        VEKTOR is a technical security tool intended for professionals and
        researchers. It is not directed at children under the age of 13.
      </p>
    </LegalPage>
  )
}
