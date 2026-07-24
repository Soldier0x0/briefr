import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import useModalLayer from '../hooks/useModalLayer.js'
import './AboutModal.css'

const SOURCES = [
  'NVD',
  'CISA KEV',
  'FIRST EPSS',
  'OSV.dev',
  'MITRE ATT&CK',
  'MITRE ATLAS',
  'SigmaHQ',
  'OTX',
  'CIRCL',
  'Sploitus',
  'VirusTotal',
  'AbuseIPDB',
  'GreyNoise',
  'MalwareBazaar',
  'URLhaus',
  'abuse.ch',
]

// Copy source: docs/PRODUCT.md § "Scope & Limits (honest by design)" — UX-L1.
const SCOPE_LIMITS = [
  {
    term: 'Single-operator, self-hosted',
    detail: 'One analyst per instance, your hardware, your data. Not multi-tenant, not a cloud service — that\u2019s the privacy and control trade.',
  },
  {
    term: 'Community-source intelligence',
    detail: 'Correlation derives from OTX community pulses (ThreatFox corroboration planned). One community source is not vendor-grade attribution, and the product labels it as such in-line. Breadth of sources is bounded by what\u2019s free and self-hostable.',
  },
  {
    term: 'Community detection rules',
    detail: 'Detect prefers a local SigmaHQ index (CVE-exact, DRL-1.1). Empty means no CVE-tagged rule — not a claim of coverage. BRIEFR-generated Sigma is an experimental hunt starter only.',
  },
  {
    term: 'Term-based stack matching',
    detail: 'Fuzzy by design — vendor/product strings, not SBOM/PURL precision. Matches are labeled with the matched term so you can judge them. Precise SBOM matching is a known, deliberate non-goal at current scope.',
  },
  {
    term: 'Deterministic, LLM-free core',
    detail: 'Correlation, scoring, and scheduling are reproducible with zero AI keys. LLMs only narrate and extract at the edges, always with template fallbacks — the same input gives the same intelligence, every run.',
  },
  {
    term: 'Freshness = upstream + your scheduler',
    detail: 'Data is as current as the public feeds and your configured cadence; every intel section shows its as-of line. BRIEFR never pretends to be real-time.',
  },
  {
    term: 'Prioritization, not discovery',
    detail: 'BRIEFR explains and ranks known-CVE intel against your stack. It is not a scanner, ASM tool, or pentest platform — it doesn\u2019t find your assets or test your systems.',
  },
  {
    term: 'One box, small hardware',
    detail: 'Designed for ~2 cores / 16 GB: PostgreSQL, one process family, no Redis, no graph DB, no microservices. Operating simplicity is a feature.',
  },
]

export default function AboutModal({ onClose }) {
  const boxRef = useRef(null)

  useModalLayer(true, boxRef)

  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  function handleOverlayClick(e) {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div
      className="about-overlay"
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="about-title"
    >
      <div className="about-box" ref={boxRef} tabIndex={-1}>
        <button className="about-close" onClick={onClose} aria-label="Close (Escape)">
          &#x2715;
        </button>

        <div className="about-header">
          <div>
            <div className="about-logo" id="about-title">BRIEFR</div>
            <div className="about-subtitle">CVE Intelligence &amp; Threat Investigation</div>
          </div>
          <p className="about-description">
            Self-hosted CVE intelligence on PostgreSQL 16+. Aggregates public
            government and open-source feeds on a rolling schedule (defaults:
            NVD hourly, KEV every 15 minutes, EPSS every 6 hours; SigmaHQ
            weekly). Analyst routes require sign-in. Session cookies only —
            no analytics, no tracking.
          </p>
        </div>

        <hr className="about-divider" />

        <div className="about-sources-section">
          <span className="about-sources-label mono">// DATA SOURCES</span>
          <div className="about-sources-tags">
            {SOURCES.map(s => (
              <span key={s} className="about-source-tag mono">{s}</span>
            ))}
          </div>
          <p className="about-sources-note">
            All trademarks, service marks, logos, and data rights remain the property of their respective owners.
            SigmaHQ rules retain DRL-1.1 attribution — BRIEFR does not claim them as its own IP.
          </p>
        </div>

        <hr className="about-divider" />

        <div className="about-scope-section">
          <span className="about-sources-label mono">// SCOPE &amp; LIMITS</span>
          <p className="about-scope-intro">
            What BRIEFR is and deliberately is not — each line is a chosen constraint with a reason.
          </p>
          <ul className="about-scope-list">
            {SCOPE_LIMITS.map(item => (
              <li key={item.term} className="about-scope-item">
                <span className="about-scope-term">{item.term}.</span>{' '}
                <span className="about-scope-detail">{item.detail}</span>
              </li>
            ))}
          </ul>
          <p className="about-scope-outro">
            The trade these constraints buy: trust, reproducibility, and a system one person can actually operate and fully understand.
          </p>
        </div>

        <hr className="about-divider" />

        <div className="about-footer">
          <div className="about-footer-meta">
            <p className="about-copyright mono">
              &copy; 2026 BRIEFR &middot; Licensed under the Apache License 2.0
            </p>
            <p className="about-built-by">
              Built by{' '}
              <a
                href="https://www.linkedin.com/in/sai-harsha-vardhan/"
                target="_blank"
                rel="noopener noreferrer"
                className="about-author-link"
              >
                Sai Harsha Vardhan
              </a>
            </p>
          </div>
          <div className="about-legal-links">
            <Link to="/privacy" onClick={onClose} className="about-legal-link mono">
              Privacy Policy
            </Link>
            <span className="about-dot" aria-hidden="true">&middot;</span>
            <Link to="/terms" onClick={onClose} className="about-legal-link mono">
              Terms of Use
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
