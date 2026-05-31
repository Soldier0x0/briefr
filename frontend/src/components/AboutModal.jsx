import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import './AboutModal.css'

const SOURCES = [
  'NVD/NIST',
  'CISA KEV',
  'EPSS by FIRST.org',
  'OSV.dev',
  'GitHub Advisory',
]

export default function AboutModal({ onClose }) {
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
      <div className="about-box">
        <button className="about-close" onClick={onClose} aria-label="Close (Escape)">
          &#x2715;
        </button>

        <div className="about-logo" id="about-title">BRIEFR</div>
        <div className="about-subtitle">Free CVE Intelligence</div>

        <hr className="about-divider" />

        <p className="about-description">
          BRIEFR aggregates vulnerability data from public government and
          open-source sources every day at 06:00 IST. No account required.
          No cookies. No tracking. No cost.
        </p>

        <div className="about-sources-section">
          <span className="about-sources-label mono">// DATA SOURCES</span>
          <div className="about-sources-tags">
            {SOURCES.map(s => (
              <span key={s} className="about-source-tag mono">{s}</span>
            ))}
          </div>
        </div>

        <hr className="about-divider" />

        <p className="about-built-by">
          Built by Sai Harsha Vardhan
        </p>

        <div className="about-legal-links">
          <Link to="/privacy" onClick={onClose} className="about-legal-link mono">
            Privacy Policy
          </Link>
          <span className="about-dot" aria-hidden="true">&middot;</span>
          <Link to="/terms" onClick={onClose} className="about-legal-link mono">
            Terms of Service
          </Link>
        </div>
      </div>
    </div>
  )
}
