import { useState } from 'react'
import { copyToClipboard } from '../utils/report.js'
import { formatAbsolute } from '../utils/timezone.js'
import './CVECard.css'

function timeAgo(isoString) {
  if (!isoString) return ''
  const diff = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}

function severityClass(sev) {
  const s = (sev || '').toLowerCase()
  if (s === 'critical') return 'critical'
  if (s === 'high')     return 'high'
  if (s === 'medium')   return 'medium'
  if (s === 'low')      return 'low'
  return 'unknown'
}

function epssColor(score) {
  if (score >= 0.7) return 'var(--red)'
  if (score >= 0.3) return 'var(--amber)'
  return 'var(--green)'
}

export default function CVECard({ cve, onSelect, selected, onToggleSelect, timezone = 'UTC' }) {
  const [shareCopied, setShareCopied] = useState(false)
  const sevClass = severityClass(cve.severity)
  const epss = typeof cve.epss_score === 'number' ? cve.epss_score : null
  const products = Array.isArray(cve.affected_products) ? cve.affected_products : []
  const cwes = Array.isArray(cve.cwe_ids) ? cve.cwe_ids : []

  function handleClick() {
    if (onSelect) onSelect(cve)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      if (onSelect) onSelect(cve)
    }
  }

  function handleCheckChange(e) {
    e.stopPropagation()
    if (onToggleSelect) onToggleSelect(cve)
  }

  function handleCheckClick(e) {
    e.stopPropagation()
  }

  async function handleShare(e) {
    e.stopPropagation()
    const desc = (cve.description || '').slice(0, 60).trimEnd()
    const url = `https://projectjupiter.in/cve/${cve.cve_id}`
    const text = `${cve.cve_id} — ${desc}\nvia VEKTOR: ${url}`
    const ok = await copyToClipboard(text)
    if (ok) {
      setShareCopied(true)
      setTimeout(() => setShareCopied(false), 1500)
    }
  }

  return (
    <article
      className={`cve-card sev-${sevClass}${selected ? ' cve-selected' : ''}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="button"
      aria-label={`CVE ${cve.cve_id}, severity ${cve.severity || 'unknown'}. Click to view details.`}
    >
      {/* Custom rectangular checkbox — top-left, hover-only */}
      <label
        className="card-checkbox-wrap"
        onClick={handleCheckClick}
        aria-label={`Select ${cve.cve_id} for bulk report`}
      >
        <input
          type="checkbox"
          className="card-checkbox-input"
          checked={!!selected}
          onChange={handleCheckChange}
          tabIndex={-1}
        />
        <span className="card-checkbox-box" aria-hidden="true" />
      </label>

      {/* Share button — top-right, hover-only */}
      <div className="card-share-wrap">
        <button
          className="card-share-btn"
          onClick={handleShare}
          aria-label={`Copy share link for ${cve.cve_id}`}
          tabIndex={-1}
        >
          &#x2197;
        </button>
        {shareCopied && (
          <span className="share-tooltip mono" role="status" aria-live="polite">
            Link copied
          </span>
        )}
      </div>

      {/* Top row: ID + badges */}
      <div className="cve-top">
        <span className="cve-id" aria-label={`CVE ID: ${cve.cve_id}`}>
          {cve.cve_id}
        </span>
        <div className="cve-badges" aria-label="CVE attributes">
          {cve.is_kev && (
            <span className="badge badge-kev" title="Listed in CISA Known Exploited Vulnerabilities">
              KEV
            </span>
          )}
          {!cve.patch_available && (
            <span className="badge badge-poc" title="No patch available — exploit may be public">
              PoC
            </span>
          )}
          {cve.cvss_score != null && (
            <span
              className={`badge badge-cvss badge-cvss-${sevClass}`}
              title={`CVSS score: ${cve.cvss_score} (${cve.severity})`}
            >
              CVSS {cve.cvss_score.toFixed(1)}
            </span>
          )}
          {cve.patch_available && (
            <span className="badge badge-patch" title="Patch available">
              Patch
            </span>
          )}
        </div>
      </div>

      {/* Description */}
      {cve.description && (
        <p className="cve-description">
          {cve.description.length > 280
            ? cve.description.slice(0, 280) + '...'
            : cve.description}
        </p>
      )}

      {/* Plain English summary */}
      {cve.summary && (
        <blockquote className="cve-summary" aria-label="Plain English summary">
          {cve.summary}
        </blockquote>
      )}

      {/* EPSS bar */}
      {epss != null && epss > 0 && (
        <div className="cve-epss" aria-label={`EPSS exploitation probability: ${(epss * 100).toFixed(1)}%`}>
          <div className="epss-track" role="progressbar" aria-valuenow={Math.round(epss * 100)} aria-valuemin={0} aria-valuemax={100}>
            <div
              className="epss-fill"
              style={{ width: `${Math.min(epss * 100, 100)}%`, background: epssColor(epss) }}
            />
          </div>
          <span className="epss-label">EPSS {(epss * 100).toFixed(1)}%</span>
        </div>
      )}

      {/* Meta row */}
      <div className="cve-meta">
        {products.length > 0 && (
          <span className="meta-item" aria-label={`Affected: ${products.slice(0, 3).join(', ')}`}>
            <span className="meta-key">affects</span>
            <span className="meta-val">
              {products.slice(0, 3).map(p => p.split(':')[1] || p).join(', ')}
              {products.length > 3 && ` +${products.length - 3}`}
            </span>
          </span>
        )}
        {cwes.length > 0 && (
          <span className="meta-item" aria-label={`Weakness: ${cwes[0]}`}>
            <span className="meta-key">weakness</span>
            <span className="meta-val">{cwes[0]}</span>
          </span>
        )}
        {cve.mitre_technique && (
          <span className="meta-item" aria-label={`MITRE technique: ${cve.mitre_technique}`}>
            <span className="meta-key">technique</span>
            <span className="meta-val">{cve.mitre_technique}</span>
          </span>
        )}
        <span className="meta-item meta-time" aria-label={`Published: ${cve.published}`}>
          <span className="meta-key">published</span>
          <span
            className="meta-val time-tooltip-wrap"
            title={formatAbsolute(cve.published, timezone)}
          >
            {timeAgo(cve.published)}
          </span>
        </span>
      </div>
    </article>
  )
}
