import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import useModalLayer from '../hooks/useModalLayer.js'
import './AboutModal.css'

const SOURCES = [
  'NVD',
  'CISA KEV',
  'FIRST EPSS',
  'MITRE ATT&CK',
  'MITRE ATLAS',
  'OTX',
  'VirusTotal',
  'AbuseIPDB',
  'GreyNoise',
  'MalwareBazaar',
  'URLhaus',
  'abuse.ch',
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

        <div className="about-logo" id="about-title">BRIEFR</div>
        <div className="about-subtitle">CVE Intelligence &amp; Threat Investigation</div>

        <hr className="about-divider" />

        <p className="about-description">
          BRIEFR aggregates vulnerability data from public government and
          open-source sources on a rolling schedule (NVD hourly, KEV every
          15 minutes, EPSS every 6 hours). Runs on PostgreSQL (production: version 16+).
          No account required.
          No cookies. No tracking.
        </p>

        <div className="about-sources-section">
          <span className="about-sources-label mono">Data sources</span>
          <div className="about-sources-tags">
            {SOURCES.map(s => (
              <span key={s} className="about-source-tag mono">{s}</span>
            ))}
          </div>
          <p className="about-sources-note">
            All trademarks, service marks, logos, and data rights remain the property of their respective owners.
          </p>
        </div>

        <hr className="about-divider" />

        <p className="about-copyright mono">
          &copy; 2026 BRIEFR &middot; Proprietary Software &middot; All Rights Reserved
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
  )
}
