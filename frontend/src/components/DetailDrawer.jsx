import { useEffect, useState } from 'react'
import { buildSingleReport, copyToClipboard } from '../utils/report.js'
import './DetailDrawer.css'

// ── Helpers ───────────────────────────────────────────────
function severityColor(sev) {
  const s = (sev || '').toUpperCase()
  if (s === 'CRITICAL') return 'var(--red)'
  if (s === 'HIGH')     return 'var(--amber)'
  if (s === 'MEDIUM')   return 'var(--accent)'
  if (s === 'LOW')      return 'var(--green)'
  return 'var(--text3)'
}


function cvssMetricColor(score, severity) {
  const fromSev = severityColor(severity)
  if ((severity || '').toUpperCase() !== 'UNKNOWN') return fromSev
  if (score == null) return 'var(--text3)'
  if (score >= 9.0) return 'var(--red)'
  if (score >= 7.0) return 'var(--amber)'
  if (score >= 4.0) return 'var(--accent)'
  if (score > 0) return 'var(--green)'
  return 'var(--text3)'
}

function epssDisplay(score) {
  if (score == null || score === undefined) return null
  return `${(score * 100).toFixed(1)}%`
}

function mitreUrl(id) {
  if (!id) return null
  const clean = id.replace(/\./g, '/')
  return `https://attack.mitre.org/techniques/${clean}`
}

// ── Metrics cell ──────────────────────────────────────────
function MetricCell({ label, value, color }) {
  return (
    <div className="metric-cell" aria-label={`${label}: ${value}`}>
      <div className="metric-value" style={{ color: color || 'var(--text)' }}>
        {value}
      </div>
      <div className="metric-label">{label}</div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────
export default function DetailDrawer({ cve, onClose }) {
  const [copied, setCopied] = useState(false)
  const isOpen = !!cve

  // Prevent body scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [isOpen])

  async function handleCopyReport() {
    if (!cve) return
    const ok = await copyToClipboard(buildSingleReport(cve))
    if (ok) {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (!cve) {
    return (
      <div className={`drawer-overlay`} aria-hidden="true" />
    )
  }

  const products = Array.isArray(cve.affected_products) ? cve.affected_products : []
  const cwes     = Array.isArray(cve.cwe_ids) ? cve.cwe_ids : []
  const urls     = Array.isArray(cve.source_urls) ? cve.source_urls.slice(0, 5) : []
  const epss     = epssDisplay(cve.epss_score)
  const sevColor = severityColor(cve.severity)
  const cvssValColor = cvssMetricColor(cve.cvss_score, cve.severity)

  return (
    <>
      {/* Overlay */}
      <div
        className="drawer-overlay drawer-overlay-active"
        onClick={onClose}
        aria-label="Close CVE detail drawer"
        role="presentation"
      />

      {/* Panel */}
      <aside
        className="drawer-panel drawer-panel-open"
        role="complementary"
        aria-label={`CVE detail: ${cve.cve_id}`}
      >
        {/* ── Header ── */}
        <div className="drawer-header">
          <div className="drawer-header-left">
            <span className="drawer-cve-id mono" aria-label={`CVE ID: ${cve.cve_id}`}>
              {cve.cve_id}
            </span>
            {cve.severity && (
              <span
                className="drawer-sev-badge mono"
                style={{ color: sevColor, borderColor: sevColor }}
                aria-label={`Severity: ${cve.severity}`}
              >
                {cve.severity}
              </span>
            )}
          </div>
          <button
            className="drawer-close"
            onClick={onClose}
            aria-label="Close drawer (Escape)"
          >
            &#x2715;
          </button>
        </div>

        <div className="drawer-body">
          {/* ── Description ── */}
          {cve.description && (
            <section className="drawer-section" aria-labelledby="desc-heading">
              <h2 id="desc-heading" className="drawer-section-label">DESCRIPTION</h2>
              <p className="drawer-description">{cve.description}</p>
            </section>
          )}

          {/* ── Plain English ── */}
          {cve.summary && (
            <section className="drawer-section" aria-labelledby="plain-heading">
              <h2 id="plain-heading" className="drawer-section-label">// PLAIN ENGLISH</h2>
              <blockquote className="drawer-summary">
                {cve.summary}
              </blockquote>
            </section>
          )}

          {/* ── Metrics ── */}
          <section className="drawer-section" aria-labelledby="metrics-heading">
            <h2 id="metrics-heading" className="drawer-section-label">METRICS</h2>
            <div className="metrics-row">
              {cve.cvss_score != null ? (
                <MetricCell
                  label="CVSS"
                  value={cve.cvss_score.toFixed(1)}
                  color={cvssValColor}
                />
              ) : (
                <MetricCell label="CVSS" value="N/A" color="var(--text3)" />
              )}
              <MetricCell
                label="EPSS"
                value={epss ?? 'N/A'}
                color={
                  epss == null
                    ? 'var(--text3)'
                    : parseFloat(epss) >= 50
                      ? 'var(--red)'
                      : parseFloat(epss) >= 20
                        ? 'var(--amber)'
                        : 'var(--green)'
                }
              />
              <MetricCell
                label="CISA KEV"
                value={cve.is_kev ? 'YES' : 'NO'}
                color={cve.is_kev ? 'var(--red)' : 'var(--text3)'}
              />
              <MetricCell
                label="PATCH"
                value={cve.patch_available ? 'YES' : 'NO'}
                color={cve.patch_available ? 'var(--green)' : 'var(--amber)'}
              />
            </div>
          </section>

          {/* ── Affected products ── */}
          {products.length > 0 && (
            <section className="drawer-section" aria-labelledby="affected-heading">
              <h2 id="affected-heading" className="drawer-section-label">AFFECTED PRODUCTS</h2>
              <div className="product-tags" aria-label="Affected products">
                {products.map(p => (
                  <span key={p} className="product-tag mono" title={p}>
                    {p.split(':')[1] || p}
                  </span>
                ))}
              </div>
              {cwes.length > 0 && (
                <div className="cwe-list" aria-label="Weakness types">
                  {cwes.map(c => (
                    <span key={c} className="cwe-tag mono">{c}</span>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* ── MITRE ATT&CK ── */}
          {cve.mitre_technique && (
            <section className="drawer-section" aria-labelledby="mitre-heading">
              <h2 id="mitre-heading" className="drawer-section-label">MITRE ATT&CK</h2>
              <div className="mitre-card" role="group" aria-label={`MITRE technique: ${cve.mitre_technique}`}>
                <span className="mitre-id mono">{cve.mitre_technique}</span>
                <a
                  className="mitre-link mono"
                  href={mitreUrl(cve.mitre_technique)}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={`View ${cve.mitre_technique} on MITRE ATT&CK (opens new tab)`}
                >
                  View on ATT&CK &rarr;
                </a>
              </div>
            </section>
          )}

          {/* ── References ── */}
          {urls.length > 0 && (
            <section className="drawer-section" aria-labelledby="refs-heading">
              <h2 id="refs-heading" className="drawer-section-label">REFERENCES</h2>
              <ul className="refs-list" aria-label="Source references">
                {urls.map(url => (
                  <li key={url} className="refs-item">
                    <a
                      className="refs-link mono"
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={`Reference: ${url}`}
                    >
                      {url}
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* ── Copy report ── */}
          <section className="drawer-section drawer-section-action">
            <button
              className={`copy-report-btn${copied ? ' copied' : ''}`}
              onClick={handleCopyReport}
              aria-label="Copy CVE report as Markdown to clipboard"
            >
              {copied ? 'Copied to clipboard!' : 'Copy as report'}
            </button>
            <span className="copy-hint mono">
              Copies Markdown report to clipboard
            </span>
          </section>
        </div>
      </aside>
    </>
  )
}
