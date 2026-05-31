import LegalPage from './LegalPage.jsx'

const SECTIONS = [
  {
    paragraphs: [
      'VEKTOR is a self-hosted, open-source CVE intelligence platform. This Privacy Policy explains what data is processed when you use VEKTOR and what is shared with third-party services.',
    ],
  },
  {
    heading: '1. Data We Do Not Collect',
    paragraphs: [
      'VEKTOR does not collect, store, or process any personally identifiable information about its users.',
    ],
    list: [
      'No user accounts or registration',
      'No cookies or tracking pixels',
      'No analytics or usage telemetry',
      'No IP address logging',
      'No session or browser fingerprinting',
      'No advertising or retargeting',
    ],
  },
  {
    heading: '2. IOC Lookups and Third-Party Services',
    paragraphs: [
      'When you use the IOC Lookup feature, the value you enter (IP address, file hash, or domain name) is sent to the following third-party services for threat intelligence enrichment:',
    ],
    list: [
      'VirusTotal (Google LLC) — https://www.virustotal.com/about/terms-of-service/',
      'AbuseIPDB — https://www.abuseipdb.com/privacy-policy',
    ],
  },
  {
    heading: '3. Local Cache',
    paragraphs: [
      'To reduce the number of requests to third-party services, IOC lookup results are stored in a local SQLite database on your server for 6 hours. This cache contains the IOC value and the enrichment result. The cache is stored locally and is never transmitted to VEKTOR or any other party.',
      'You are informed of this caching in the IOC Lookup interface.',
    ],
  },
  {
    heading: '4. CVE Data Sources',
    paragraphs: [
      'VEKTOR retrieves vulnerability data from the following public sources. No personal data is transmitted to these sources during normal operation:',
    ],
    list: [
      'NVD (National Vulnerability Database) — operated by NIST, US Government',
      'CISA Known Exploited Vulnerabilities — operated by CISA, US Government',
      'EPSS (Exploit Prediction Scoring System) — operated by FIRST.org',
      'OSV.dev — operated by Google LLC',
    ],
  },
  {
    heading: '5. Data Retention',
    paragraphs: [
      'CVE data fetched from public sources is stored in a local SQLite database and refreshed daily. IOC cache entries expire after 6 hours. No data is sent to VEKTOR servers — VEKTOR has no central servers; you operate your own instance.',
    ],
  },
  {
    heading: '6. Contact',
    paragraphs: [
      'VEKTOR is open source and self-hosted. For questions about this Privacy Policy or the project, contact the maintainer via GitHub: https://github.com/Soldier0x0',
    ],
  },
]

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      lastUpdated="May 2026"
      sections={SECTIONS}
    />
  )
}
