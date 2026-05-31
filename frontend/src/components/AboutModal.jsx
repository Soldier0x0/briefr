import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import './AboutModal.css'

const SOURCES = ['NVD / NIST', 'CISA KEV', 'EPSS by FIRST.org', 'OSV.dev']

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
        <button
          className="about-close"
          onClick={onClose}
          aria-label="Close about modal (Escape)"
        >
          &#x2715;
        </button>

        <div className="about-logo" aria-label="VEKTOR">VEKTOR</div>
        <div className="about-subtitle">Free CVE Intelligence</div>

        <hr className="about-divider" />

        <p className="about-description">
          VEKTOR aggregates vulnerability data from public government and
          open-source sources daily. No account required. No tracking. No cost.
        </p>

        <div className="about-sources-section">
          <span className="about-sources-label mono">DATA SOURCES</span>
          <div className="about-sources-tags">
            {SOURCES.map(s => (
              <span key={s} className="about-source-tag mono">{s}</span>
            ))}
          </div>
        </div>

        <p className="about-built-by">
          Built by{' '}
          <a
            href="https://github.com/Soldier0x0"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Sai Harsha Vardhan on GitHub"
          >
            Sai Harsha Vardhan
          </a>
        </p>

        <div className="about-legal-links">
          <Link to="/privacy" onClick={onClose} aria-label="Privacy Policy">
            Privacy Policy
          </Link>
          <span className="about-dot" aria-hidden="true">&middot;</span>
          <Link to="/terms" onClick={onClose} aria-label="Terms of Service">
            Terms of Service
          </Link>
        </div>
      </div>
    </div>
  )
}
