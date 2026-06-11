import { useState, useEffect, useRef } from 'react'
import { getReportTimestamp } from '../utils/timezone.js'
import useModalLayer from '../hooks/useModalLayer.js'
import './DigestModal.css'

function severityTag(sev) {
  const s = (sev || '').toUpperCase()
  if (s === 'CRITICAL') return '[CRIT]'
  if (s === 'HIGH')     return '[HIGH]'
  if (s === 'MEDIUM')   return '[MED] '
  if (s === 'LOW')      return '[LOW] '
  return '[????]'
}

function buildDigest(cves, filters) {
  const now = new Date()
  const dateStr = now.toISOString().split('T')[0]
  const timeStr = getReportTimestamp()

  const activeFilters = []
  if (filters.severity) activeFilters.push(filters.severity)
  if (filters.kev_only) activeFilters.push('KEV')
  if (filters.poc_only) activeFilters.push('PoC')
  if (filters.epss_min) activeFilters.push(`EPSS>${filters.epss_min * 100}%`)
  if (filters.search)   activeFilters.push(`search:"${filters.search}"`)
  if (filters.my_stack_only) activeFilters.push('my-stack')
  if (filters.summary_only) activeFilters.push('plain-english')
  if (filters.stack)    activeFilters.push(`stack:"${filters.stack}"`)
  if (filters.vendors)  activeFilters.push(`vendors:${filters.vendors}`)
  const filterStr = activeFilters.length > 0 ? activeFilters.join(', ') : 'none'

  const header = [
    `BRIEFR — CVE DIGEST`,
    `Date:      ${dateStr}`,
    `Generated: ${timeStr}`,
    `Filters: ${filterStr}`,
    ``,
    `${cves.length} CVEs matching current filters`,
    ``,
    `---`,
    ``,
  ].join('\n')

  const lines = cves.map(cve => {
    const tag  = severityTag(cve.severity)
    const id   = cve.cve_id.padEnd(18)
    const cvss = cve.cvss_score != null
      ? `CVSS ${cve.cvss_score.toFixed(1)}`
      : 'CVSS ---'
    const desc = (cve.description || '').replace(/\n/g, ' ').slice(0, 80)
    return `${tag} ${id} ${cvss}  ${desc}`
  }).join('\n')

  return header + lines
}

export default function DigestModal({ cves, filters, onClose }) {
  const [copied, setCopied] = useState(false)
  const textRef = useRef(null)
  const panelRef = useRef(null)
  const copiedTimerRef = useRef(null)
  const digest = buildDigest(cves, filters)

  useModalLayer(true, panelRef)

  // Scroll page to top so modal is visible (required since overlay is absolute, not fixed)
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [])

  useEffect(() => () => {
    if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current)
  }, [])

  function flashCopied() {
    setCopied(true)
    if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current)
    copiedTimerRef.current = setTimeout(() => setCopied(false), 2000)
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(digest)
      flashCopied()
    } catch {
      if (textRef.current) {
        textRef.current.select()
        document.execCommand('copy')
        flashCopied()
      }
    }
  }

  return (
    /* Full-height wrapper — no position:fixed per spec */
    <div className="digest-overlay" role="dialog" aria-modal="true" aria-labelledby="digest-title">
      <div className="digest-panel" ref={panelRef} tabIndex={-1}>
        <div className="digest-header">
          <div className="digest-header-left">
            <h2 id="digest-title" className="digest-title mono">BRIEFR DIGEST</h2>
            <span className="digest-count mono" aria-label={`${cves.length} CVEs`}>
              {cves.length} CVEs
            </span>
          </div>
          <button
            className="digest-close"
            onClick={onClose}
            aria-label="Close digest (Escape)"
          >
            &#x2715;
          </button>
        </div>

        <textarea
          ref={textRef}
          className="digest-textarea mono"
          value={digest}
          readOnly
          aria-label="Generated CVE digest — copy this text"
          spellCheck="false"
        />

        <div className="digest-actions">
          <button
            className={`digest-action-btn digest-copy-btn${copied ? ' copied' : ''}`}
            onClick={handleCopy}
            aria-label="Copy digest to clipboard"
          >
            {copied ? 'Copied!' : 'COPY'}
          </button>
          <button
            className="digest-action-btn"
            onClick={onClose}
            aria-label="Close digest modal"
          >
            CLOSE
          </button>
          <span className="digest-hint mono">
            Press Escape to close
          </span>
        </div>
      </div>
    </div>
  )
}
