import { useState, useRef, useEffect, useCallback } from 'react'
import { lookupIOC } from '../api.js'
import './IOCLookup.css'

// ── Type detection ────────────────────────────────────────
const IPV4_RE     = /^(\d{1,3}\.){3}\d{1,3}$/
const HASH_RE     = /^[0-9a-fA-F]{32}$|^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$/
const DOMAIN_RE   = /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$/

function detectType(val) {
  const v = val.trim()
  if (!v) return null
  if (IPV4_RE.test(v))   return 'ip'
  if (HASH_RE.test(v))   return 'hash'
  if (DOMAIN_RE.test(v)) return 'domain'
  return null
}

// ── Verdict helpers ───────────────────────────────────────
function verdictInfo(malicious, total) {
  if (!total) return { label: 'unknown', color: 'var(--text3)', pct: 0 }
  const pct = malicious / total
  if (pct < 0.1) return { label: 'clean',      color: 'var(--green)', pct }
  if (pct < 0.5) return { label: 'suspicious', color: 'var(--amber)', pct }
  return               { label: 'malicious',   color: 'var(--red)',   pct }
}

// ── Error message mapping ─────────────────────────────────
function parseError(err) {
  if (err.status === 0)   return 'Network error — is the backend running?'
  if (err.status === 403) return 'Invalid API key — check your .env file'
  if (err.status === 429) return 'Rate limit reached — try again in 60 seconds'
  if (err.status === 404) return 'Not found in threat databases'
  if (err.status === 422) return 'Invalid input — check the value and type'
  return err.message || 'Lookup failed — unknown error'
}

// ── Sub-components ────────────────────────────────────────
const IOC_TYPES = [
  { id: 'ip',     label: 'IP ADDRESS' },
  { id: 'hash',   label: 'FILE HASH'  },
  { id: 'domain', label: 'DOMAIN'     },
]

function TypeSelector({ selected, onChange, detected }) {
  return (
    <div className="ioc-type-selector" role="group" aria-label="IOC type">
      {IOC_TYPES.map(t => (
        <button
          key={t.id}
          className={[
            'ioc-type-btn',
            selected === t.id ? 'selected' : '',
            detected === t.id && selected !== t.id ? 'detected' : '',
          ].filter(Boolean).join(' ')}
          onClick={() => onChange(t.id)}
          aria-pressed={selected === t.id}
          aria-label={`Set type to ${t.label}`}
          title={detected === t.id ? 'Auto-detected' : undefined}
        >
          {t.label}
          {detected === t.id && (
            <span className="detected-mark" aria-label="auto-detected">*</span>
          )}
        </button>
      ))}
    </div>
  )
}

function ThreatBar({ malicious, total }) {
  const { label, color, pct } = verdictInfo(malicious, total)
  const fillPct = Math.min(pct * 100, 100)

  return (
    <div className="threat-bar-section" aria-label={`Threat score: ${malicious} of ${total} engines flagged`}>
      <div className="threat-bar-header">
        <span className="threat-ratio" style={{ color }}>
          <span className="threat-num">{malicious}</span>
          <span className="threat-sep"> / </span>
          <span className="threat-total">{total}</span>
          <span className="threat-label"> engines flagged</span>
        </span>
        <span className="verdict-badge" style={{ color, borderColor: color }} aria-label={`Verdict: ${label}`}>
          {label.toUpperCase()}
        </span>
      </div>
      <div
        className="threat-track"
        role="progressbar"
        aria-valuenow={Math.round(fillPct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${Math.round(fillPct)}% of engines flagged`}
      >
        <div
          className="threat-fill"
          style={{ width: `${fillPct}%`, background: color }}
        />
      </div>
    </div>
  )
}

function DetailGrid({ result }) {
  const tags = Array.isArray(result.tags) ? result.tags.filter(Boolean) : []
  const lastSeen = result.last_seen
    ? (() => {
        const n = Number(result.last_seen)
        const d = isNaN(n) ? new Date(result.last_seen) : new Date(n * 1000)
        return isNaN(d.getTime()) ? result.last_seen : d.toISOString().split('T')[0]
      })()
    : null

  const rows = [
    { key: 'type',           val: result.type?.toUpperCase() },
    { key: 'country',        val: result.country,                   show: !!result.country },
    { key: 'last seen',      val: lastSeen,                         show: !!lastSeen },
    { key: 'abuse score',    val: result.abuse_score != null ? `${result.abuse_score} / 100` : null, show: result.abuse_score != null },
  ].filter(r => r.show !== false && r.val != null)

  return (
    <div className="detail-grid" aria-label="IOC details">
      {rows.map(r => (
        <div key={r.key} className="detail-row">
          <span className="detail-key">{r.key}</span>
          <span className="detail-val mono">{r.val}</span>
        </div>
      ))}
      {tags.length > 0 && (
        <div className="detail-row detail-row-tags">
          <span className="detail-key">tags</span>
          <div className="tags-list" aria-label={`Tags: ${tags.join(', ')}`}>
            {tags.map(tag => (
              <span key={tag} className="ioc-tag mono">{tag}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ActionRow({ result, onCopy, copied }) {
  const hasVTLink = !!result.vt_link

  return (
    <div className="action-row">
      {hasVTLink && (
        <a
          className="action-btn action-btn-primary"
          href={result.vt_link}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="View this IOC on VirusTotal (opens new tab)"
        >
          View on VirusTotal &rarr;
        </a>
      )}
      <button
        className={`action-btn${copied ? ' action-btn-copied' : ''}`}
        onClick={onCopy}
        aria-label="Copy report to clipboard"
      >
        {copied ? 'Copied!' : 'Copy report'}
      </button>
    </div>
  )
}

function HistoryItem({ item, onRerun }) {
  const { label, color } = verdictInfo(item.malicious, item.total)

  return (
    <button
      className="history-item"
      onClick={() => onRerun(item)}
      aria-label={`Re-run lookup for ${item.value}, verdict: ${label}`}
    >
      <span className="history-value mono">{item.value}</span>
      <div className="history-badges">
        <span className="history-type-badge mono">{item.iocType.toUpperCase()}</span>
        <span className="history-verdict-badge mono" style={{ color, borderColor: color }}>
          {label}
        </span>
      </div>
    </button>
  )
}

// ── Main component ────────────────────────────────────────
export default function IOCLookup() {
  const [value, setValue]       = useState('')
  const [iocType, setIocType]   = useState('ip')
  const [detected, setDetected] = useState(null)
  const [loading, setLoading]   = useState(false)
  const [result, setResult]     = useState(null)
  const [error, setError]       = useState(null)
  const [copied, setCopied]     = useState(false)
  const [history, setHistory]   = useState([])   // session-only, no localStorage

  const detectDebounce = useRef(null)

  // Auto-detect type after 500ms pause
  const handleValueChange = useCallback((e) => {
    const val = e.target.value
    setValue(val)
    if (detectDebounce.current) clearTimeout(detectDebounce.current)
    detectDebounce.current = setTimeout(() => {
      const t = detectType(val)
      setDetected(t)
      if (t) setIocType(t)
    }, 500)
  }, [])

  // Clean up debounce on unmount
  useEffect(() => () => {
    if (detectDebounce.current) clearTimeout(detectDebounce.current)
  }, [])

  async function runLookup(lookupValue, lookupType) {
    const trimmed = (lookupValue ?? value).trim()
    const type    = lookupType ?? iocType
    if (!trimmed) return

    setLoading(true)
    setResult(null)
    setError(null)

    try {
      const data = await lookupIOC(trimmed, type)

      // Surface backend-level auth/not-found errors
      if (data.error) {
        const msg = data.error.toLowerCase()
        if (msg.includes('auth') || msg.includes('key')) {
          setError('Invalid API key — check your .env file')
        } else if (msg.includes('not found') || msg.includes('404')) {
          setError('Not found in threat databases')
        } else {
          // Show result even if there's a partial error
          setResult(data)
        }
      } else {
        setResult(data)
      }

      // Add to session history (deduplicate by value, cap at 5)
      const verdict = verdictInfo(data.malicious_votes, data.total_votes)
      setHistory(prev => {
        const filtered = prev.filter(h => h.value !== trimmed)
        return [
          {
            value: trimmed,
            iocType: type,
            malicious: data.malicious_votes ?? 0,
            total: data.total_votes ?? 0,
            verdict: verdict.label,
          },
          ...filtered,
        ].slice(0, 5)
      })
    } catch (err) {
      setError(parseError(err))
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') runLookup()
  }

  function handleRerun(item) {
    setValue(item.value)
    setIocType(item.iocType)
    setDetected(detectType(item.value))
    runLookup(item.value, item.iocType)
  }

  async function copyReport() {
    if (!result) return
    const { label } = verdictInfo(result.malicious_votes, result.total_votes)
    const tags = (result.tags || []).join(', ') || 'none'
    const lines = [
      'IOC Report — BRIEFR',
      `Type:    ${result.type?.toUpperCase()}`,
      `Value:   ${result.value}`,
      `Verdict: ${label.toUpperCase()}`,
      `Score:   ${result.malicious_votes ?? 0} / ${result.total_votes ?? 0} engines flagged`,
      result.country    ? `Country: ${result.country}` : null,
      result.abuse_score != null ? `Abuse:   ${result.abuse_score} / 100` : null,
      `Tags:    ${tags}`,
      result.vt_link    ? `Report:  ${result.vt_link}` : null,
      '',
      'Source: BRIEFR — VirusTotal + AbuseIPDB',
    ].filter(l => l !== null).join('\n')

    try {
      await navigator.clipboard.writeText(lines)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard may be unavailable in some browser contexts
    }
  }

  const hasResult = !!result && !error

  return (
    <section className="ioc-lookup" aria-label="IOC threat intelligence lookup">

      {/* ── Page header ── */}
      <div className="ioc-page-header">
        <h1 className="ioc-page-title">IOC LOOKUP</h1>
        <p className="ioc-page-sub">
          Enrich indicators of compromise against VirusTotal and AbuseIPDB.
          Paste an IP address, file hash, or domain name below.
        </p>
      </div>

      {/* ── Input section ── */}
      <div className="ioc-input-section">
        <label htmlFor="ioc-value-input" className="ioc-input-label">
          // INDICATOR
        </label>
        <textarea
          id="ioc-value-input"
          className="ioc-value-input mono"
          value={value}
          onChange={handleValueChange}
          onKeyDown={handleKeyDown}
          placeholder="8.8.8.8  /  d41d8cd98f00b204e9800998ecf8427e  /  example.com"
          aria-label="Enter IOC value — IP address, file hash, or domain"
          rows={3}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck="false"
        />

        <div className="ioc-controls">
          <TypeSelector
            selected={iocType}
            onChange={setIocType}
            detected={detected}
          />
          <button
            className="ioc-lookup-btn"
            onClick={() => runLookup()}
            disabled={loading || !value.trim()}
            aria-label="Run IOC lookup"
          >
            {loading ? (
              <span className="btn-loading" aria-label="Searching...">
                <span /><span /><span />
              </span>
            ) : 'LOOKUP'}
          </button>
        </div>

        <p className="ioc-privacy-notice mono" role="note">
          {'// Lookups are sent to VirusTotal and AbuseIPDB. Results cached'}<br />
          {'// locally for 6h. No user data is stored. See Privacy Policy.'}
        </p>
      </div>

      {/* ── Error state ── */}
      {error && (
        <div className="ioc-error-block" role="alert" aria-live="assertive">
          <span className="ioc-error-mark mono" aria-hidden="true">ERR</span>
          <span>{error}</span>
        </div>
      )}

      {/* ── Results ── */}
      {hasResult && (
        <div className="ioc-results" aria-label={`Results for ${result.value}`}>
          <div className="ioc-results-header">
            <span className="result-value mono" aria-label={`IOC: ${result.value}`}>
              {result.value}
            </span>
            <div className="result-header-badges">
              <span className="result-type-badge mono">
                {result.type?.toUpperCase()}
              </span>
              {result.cached && (
                <span className="result-cached-badge mono" title="Served from 6h cache">
                  CACHED
                </span>
              )}
            </div>
          </div>

          <ThreatBar
            malicious={result.malicious_votes ?? 0}
            total={result.total_votes ?? 0}
          />

          <DetailGrid result={result} />

          <ActionRow result={result} onCopy={copyReport} copied={copied} />
        </div>
      )}

      {/* ── History ── */}
      {history.length > 0 && (
        <div className="ioc-history" aria-label="Recent lookups this session">
          <h2 className="ioc-history-heading mono">// RECENT</h2>
          <div className="history-list" role="list">
            {history.map(item => (
              <div key={item.value} role="listitem">
                <HistoryItem item={item} onRerun={handleRerun} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Idle state ── */}
      {!hasResult && !error && !loading && history.length === 0 && (
        <div className="ioc-idle" aria-label="Awaiting input">
          <div className="idle-flow mono" aria-hidden="true">
            <span className="idle-node">INDICATOR</span>
            <span className="idle-arrow">--&gt;</span>
            <span className="idle-node">VIRUSTOTAL</span>
            <span className="idle-arrow">+</span>
            <span className="idle-node">ABUSEIPDB</span>
            <span className="idle-arrow">--&gt;</span>
            <span className="idle-node">VERDICT</span>
          </div>
          <p>Enter an IP, file hash, or domain above and press LOOKUP.</p>
        </div>
      )}

    </section>
  )
}
