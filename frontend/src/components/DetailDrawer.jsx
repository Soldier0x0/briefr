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

function techniqueLink(tech) {
  if (tech?.url) return tech.url
  const id = tech?.id || tech?.technique_id
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

  // C — copy report while drawer is open
  useEffect(() => {
    if (!isOpen) return
    function onKey(e) {
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.key === 'c' || e.key === 'C') {
        e.preventDefault()
        handleCopyReport()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [isOpen, cve])

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
  const techniques = Array.isArray(cve.techniques) ? cve.techniques : []

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
          <section className="drawer-section" aria-labelledby="mitre-heading">
            <h2 id="mitre-heading" className="drawer-section-label">MITRE ATT&CK</h2>
            {techniques.length === 0 ? (
              <p className="mitre-empty mono">// No ATT&CK mapping available</p>
            ) : (
              <div className="mitre-techniques" role="list" aria-label="Mapped ATT&CK techniques">
                {techniques.map(tech => {
                  const tid = tech.id || tech.technique_id
                  const href = techniqueLink(tech)
                  return (
                    <article
                      key={tid}
                      className="mitre-technique-card"
                      role="listitem"
                      aria-label={`${tid}: ${tech.name}`}
                    >
                      <div className="mitre-technique-top">
                        <span className="mitre-technique-id mono">{tid}</span>
                        {tech.tactic && (
                          <span className="mitre-tactic-badge mono">{tech.tactic}</span>
                        )}
                      </div>
                      <p className="mitre-technique-name">{tech.name}</p>
                      {href && (
                        <a
                          className="mitre-technique-link mono"
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label={`View ${tid} on attack.mitre.org (opens new tab)`}
                        >
                          attack.mitre.org &rarr;
                        </a>
                      )}
                    </article>
                  )
                })}
              </div>
            )}
          </section>

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
