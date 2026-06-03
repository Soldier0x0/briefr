import { useEffect, useRef, useState } from 'react'
import { fetchCVESentences } from '../api.js'
import { buildSingleReport, copyToClipboard } from '../utils/report.js'
import './DetailDrawer.css'

const TABS = [
  { id: 'overview', label: 'OVERVIEW' },
  { id: 'intel', label: 'INTEL' },
  { id: 'detect', label: 'DETECT' },
  { id: 'related', label: 'RELATED' },
]

function severityColor(sev) {
  const s = (sev || '').toUpperCase()
  if (s === 'CRITICAL') return 'var(--red)'
  if (s === 'HIGH')     return 'var(--amber)'
  if (s === 'MEDIUM')   return 'var(--accent)'
  if (s === 'LOW')      return 'var(--green)'
  return 'var(--text3)'
}

function techniqueLink(tech) {
  if (tech?.url) return tech.url
  const id = tech?.id || tech?.technique_id
  if (!id) return null
  const clean = id.replace(/\./g, '/')
  return `https://attack.mitre.org/techniques/${clean}`
}

function Phase2Block({ title }) {
  const headingId = `phase2-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
  return (
    <section className="drawer-section" aria-labelledby={headingId}>
      <h3 id={headingId} className="drawer-section-label">{title}</h3>
      <p className="drawer-phase2 mono">// Coming in Phase 2</p>
    </section>
  )
}

function HumanSentence({ label, text }) {
  if (!text) return null
  const headingId = `human-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
  return (
    <section className="drawer-section" aria-labelledby={headingId}>
      <h3 id={headingId} className="drawer-human-label mono">{label}</h3>
      <p className="drawer-human-text">{text}</p>
    </section>
  )
}

function buildPrintableHtml(cve) {
  const report = buildSingleReport(cve)
  const escaped = report
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${cve.cve_id} Report</title>
<style>
  body { font-family: system-ui, sans-serif; padding: 2rem; line-height: 1.5; color: #111; }
  pre { white-space: pre-wrap; font-family: ui-monospace, monospace; font-size: 12px; }
</style></head><body><pre>${escaped}</pre></body></html>`
}

function downloadPdf(cve) {
  const w = window.open('', '_blank', 'noopener,noreferrer')
  if (!w) return
  w.document.write(buildPrintableHtml(cve))
  w.document.close()
  w.focus()
  w.onload = () => {
    w.print()
  }
}

function TabOverview({ cve, products, cwes, urls, sentences, sentencesLoading }) {
  return (
    <>
      {cve.description && (
        <section className="drawer-section" aria-labelledby="desc-heading">
          <h3 id="desc-heading" className="drawer-human-label mono">DESCRIPTION</h3>
          <p className="drawer-description">{cve.description}</p>
        </section>
      )}

      {cve.summary && (
        <section className="drawer-section" aria-labelledby="plain-heading">
          <h3 id="plain-heading" className="drawer-human-label mono">PLAIN ENGLISH</h3>
          <blockquote className="drawer-summary">{cve.summary}</blockquote>
        </section>
      )}

      {sentencesLoading && (
        <section className="drawer-section">
          <p className="drawer-human-loading mono">// Loading intelligence summary...</p>
        </section>
      )}

      {sentences && (
        <>
          <HumanSentence label="RISK ASSESSMENT" text={sentences.risk} />
          <HumanSentence label="EXPLOIT LIKELIHOOD" text={sentences.exploit_likelihood} />
          <HumanSentence label="PUBLIC EXPLOITS" text={sentences.public_exploits} />
          <HumanSentence label="PATCH STATUS" text={sentences.patch} />
          <HumanSentence label="CISA KEV STATUS" text={sentences.kev} />
        </>
      )}

      {products.length > 0 && (
        <section className="drawer-section" aria-labelledby="affected-heading">
          <h3 id="affected-heading" className="drawer-human-label mono">AFFECTED PRODUCTS</h3>
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

      {urls.length > 0 && (
        <section className="drawer-section" aria-labelledby="refs-heading">
          <h3 id="refs-heading" className="drawer-human-label mono">REFERENCES</h3>
          <ul className="refs-list" aria-label="Source references">
            {urls.map(url => (
              <li key={url} className="refs-item">
                <a
                  className="refs-link mono"
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {url}
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}

function TabIntel({ techniques }) {
  return (
    <section className="drawer-section" aria-labelledby="mitre-heading">
      <h3 id="mitre-heading" className="drawer-section-label">MITRE ATT&CK</h3>
      {techniques.length === 0 ? (
        <p className="mitre-empty mono">// No ATT&CK mapping available</p>
      ) : (
        <div className="mitre-techniques" role="list" aria-label="Mapped ATT&CK techniques">
          {techniques.map(tech => {
            const tid = tech.id || tech.technique_id
            const href = techniqueLink(tech)
            return (
              <article key={tid} className="mitre-technique-card" role="listitem">
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
  )
}

function TabDetect() {
  return (
    <>
      <Phase2Block title="LOG PATTERNS" />
      <Phase2Block title="SIEM QUERY SUGGESTIONS" />
      <Phase2Block title="YARA RULE AVAILABILITY" />
    </>
  )
}

function TabRelated() {
  return <Phase2Block title="OTHER CVES — SAME PRODUCT (30 DAYS)" />
}

export default function DetailDrawer({ cve, onClose }) {
  const [activeTab, setActiveTab] = useState('overview')
  const [reportOpen, setReportOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [sentences, setSentences] = useState(null)
  const [sentencesLoading, setSentencesLoading] = useState(false)
  const reportRef = useRef(null)
  const isOpen = !!cve

  useEffect(() => {
    if (!cve?.cve_id) {
      setSentences(null)
      setSentencesLoading(false)
      return
    }
    let cancelled = false
    setSentences(null)
    setSentencesLoading(true)
    fetchCVESentences(cve.cve_id)
      .then(data => {
        if (!cancelled) setSentences(data)
      })
      .catch(() => {
        if (!cancelled) setSentences(null)
      })
      .finally(() => {
        if (!cancelled) setSentencesLoading(false)
      })
    return () => { cancelled = true }
  }, [cve?.cve_id])

  useEffect(() => {
    if (isOpen) {
      document.body.classList.add('briefr-drawer-open')
      document.body.style.overflow = 'hidden'
      setActiveTab('overview')
      setReportOpen(false)
    } else {
      document.body.classList.remove('briefr-drawer-open')
      document.body.style.overflow = ''
    }
    return () => {
      document.body.classList.remove('briefr-drawer-open')
      document.body.style.overflow = ''
    }
  }, [isOpen])

  useEffect(() => {
    if (!reportOpen) return
    function onDocClick(e) {
      if (reportRef.current && !reportRef.current.contains(e.target)) {
        setReportOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [reportOpen])

  async function handleCopyMarkdown() {
    if (!cve) return
    const ok = await copyToClipboard(buildSingleReport(cve))
    if (ok) {
      setCopied(true)
      setReportOpen(false)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  function handleDownloadPdf() {
    if (!cve) return
    downloadPdf(cve)
    setReportOpen(false)
  }

  useEffect(() => {
    if (!isOpen) return
    function onKey(e) {
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.key === 'c' || e.key === 'C') {
        e.preventDefault()
        handleCopyMarkdown()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [isOpen, cve])

  if (!cve) {
    return <div className="drawer-overlay" aria-hidden="true" />
  }

  const products = Array.isArray(cve.affected_products) ? cve.affected_products : []
  const cwes = Array.isArray(cve.cwe_ids) ? cve.cwe_ids : []
  const urls = Array.isArray(cve.source_urls) ? cve.source_urls.slice(0, 5) : []
  const sevColor = severityColor(cve.severity)
  const techniques = Array.isArray(cve.techniques) ? cve.techniques : []

  return (
    <>
      <div
        className="drawer-overlay drawer-overlay-active"
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        className="drawer-panel drawer-panel-open"
        role="dialog"
        aria-modal="true"
        aria-label={`CVE detail: ${cve.cve_id}`}
      >
        <div className="drawer-sheet-handle" aria-hidden="true" />

        <div className="drawer-chrome">
          <header className="drawer-header">
            <div className="drawer-header-left">
              <span className="drawer-cve-id mono">{cve.cve_id}</span>
              {cve.severity && (
                <span
                  className="drawer-sev-badge mono"
                  style={{ color: sevColor, borderColor: sevColor }}
                >
                  {cve.severity}
                </span>
              )}
            </div>
            <div className="drawer-header-actions">
              <div className="drawer-report-wrap" ref={reportRef}>
                <button
                  type="button"
                  className="drawer-report-btn mono"
                  onClick={() => setReportOpen(o => !o)}
                  aria-expanded={reportOpen}
                  aria-haspopup="menu"
                >
                  REPORT
                </button>
                {reportOpen && (
                  <div className="drawer-report-menu" role="menu">
                    <button
                      type="button"
                      role="menuitem"
                      className="drawer-report-item mono"
                      onClick={handleDownloadPdf}
                    >
                      Download PDF
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      className="drawer-report-item mono"
                      onClick={handleCopyMarkdown}
                    >
                      {copied ? 'Copied!' : 'Copy Markdown'}
                    </button>
                  </div>
                )}
              </div>
              <button
                type="button"
                className="drawer-close"
                onClick={onClose}
                aria-label="Close drawer (Escape)"
              >
                &#x2715;
              </button>
            </div>
          </header>

          <nav className="drawer-tabs" role="tablist" aria-label="CVE detail sections">
            {TABS.map(tab => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                id={`drawer-tab-${tab.id}`}
                className={`drawer-tab mono${activeTab === tab.id ? ' drawer-tab-active' : ''}`}
                aria-selected={activeTab === tab.id}
                aria-controls={`drawer-panel-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div
          className="drawer-tab-panel"
          role="tabpanel"
          id={`drawer-panel-${activeTab}`}
          aria-labelledby={`drawer-tab-${activeTab}`}
        >
          {activeTab === 'overview' && (
            <TabOverview
              cve={cve}
              products={products}
              cwes={cwes}
              urls={urls}
              sentences={sentences}
              sentencesLoading={sentencesLoading}
            />
          )}
          {activeTab === 'intel' && <TabIntel techniques={techniques} />}
          {activeTab === 'detect' && <TabDetect />}
          {activeTab === 'related' && <TabRelated />}
        </div>
      </aside>
    </>
  )
}
