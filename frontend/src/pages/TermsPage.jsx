import LegalPage from './LegalPage.jsx'

const SECTIONS = [
  {
    paragraphs: [
      'By accessing and using VEKTOR, you agree to be bound by these Terms of Service. If you do not agree, do not use this platform.',
    ],
  },
  {
    heading: '1. Description of Service',
    paragraphs: [
      'VEKTOR is a free, self-hosted CVE intelligence platform that aggregates publicly available vulnerability data from government and open-source sources. It is provided as-is, at no cost, for informational purposes.',
    ],
  },
  {
    heading: '2. Not a Substitute for Professional Advice',
    paragraphs: [
      'The information provided by VEKTOR — including CVE data, EPSS scores, KEV status, and IOC enrichment results — is for informational and research purposes only.',
      'VEKTOR is not a substitute for professional security advice, incident response services, or a certified vulnerability management program. Decisions about patching, remediation, or response should be made by qualified security professionals.',
    ],
  },
  {
    heading: '3. Data Accuracy',
    paragraphs: [
      'VEKTOR sources its data from NVD, CISA, FIRST.org, and OSV.dev. While these are authoritative sources, VEKTOR makes no warranty as to the completeness, accuracy, or timeliness of the data displayed.',
      'CVE data is refreshed daily. There may be a lag between a vulnerability being published and its appearance in VEKTOR.',
    ],
  },
  {
    heading: '4. Acceptable Use',
    paragraphs: [
      'You agree to use VEKTOR only for lawful purposes. You must not:',
    ],
    list: [
      'Use the platform to facilitate or plan malicious activity',
      'Attempt to overwhelm or disrupt the backend services',
      'Abuse third-party API quotas (VirusTotal, AbuseIPDB) via automated bulk IOC lookups',
      'Misrepresent VEKTOR data as real-time or authoritative threat intelligence',
    ],
  },
  {
    heading: '5. Third-Party Services',
    paragraphs: [
      'IOC lookups are forwarded to VirusTotal and AbuseIPDB. Use of these services is subject to their respective terms of service. VEKTOR is not affiliated with, endorsed by, or responsible for VirusTotal, AbuseIPDB, NIST, CISA, FIRST.org, or OSV.dev.',
    ],
  },
  {
    heading: '6. Source Attribution',
    paragraphs: [
      'CVE data is sourced from the National Vulnerability Database (NVD), operated by NIST. CISA KEV data is sourced from the US Cybersecurity and Infrastructure Security Agency. EPSS data is provided by FIRST.org. OSV data is provided by Google LLC.',
      'All trademarks belong to their respective owners.',
    ],
  },
  {
    heading: '7. Disclaimer of Warranties',
    paragraphs: [
      'VEKTOR is provided "as is" and "as available" without any warranties of any kind, express or implied, including but not limited to warranties of merchantability, fitness for a particular purpose, or non-infringement.',
    ],
  },
  {
    heading: '8. Limitation of Liability',
    paragraphs: [
      'To the maximum extent permitted by law, the VEKTOR maintainers shall not be liable for any indirect, incidental, special, or consequential damages arising from the use of or inability to use this platform.',
    ],
  },
  {
    heading: '9. Contact',
    paragraphs: [
      'Questions about these Terms of Service? Contact the maintainer via GitHub: https://github.com/Soldier0x0',
    ],
  },
]

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms of Service"
      lastUpdated="May 2026"
      sections={SECTIONS}
    />
  )
}
