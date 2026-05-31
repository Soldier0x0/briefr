import { useState } from 'react'
import { lookupIOC } from '../api.js'
import './IOCLookup.css'

const IOC_TYPES = [
  { id: 'ip',     label: 'IP ADDRESS',  placeholder: '8.8.8.8' },
  { id: 'hash',   label: 'FILE HASH',   placeholder: 'MD5 / SHA-1 / SHA-256' },
  { id: 'domain', label: 'DOMAIN',      placeholder: 'example.com' },
]

function ResultRow({ label, value, mono }) {
  if (value == null || value === '') return null
  return (
    <div className="result-row">
      <span className="result-key">{label}</span>
      <span className={`result-val${mono ? ' mono' : ''}`}>{String(value)}</span>
    </div>
  )
}

function VerdictBar({ malicious, total }) {
  if (!total) return null
  const pct = Math.round((malicious / total) * 100)
  const color = malicious === 0 ? 'var(--green)' : malicious <= 3 ? 'var(--amber)' : 'var(--red)'
  return (
    <div className="verdict-bar-wrap" aria-label={`${malicious} of ${total} engines flagged as malicious`}>
      <div className="verdict-numbers">
        <span style={{ color }} className="mono">{malicious}</span>
        <span className="verdict-sep">/</span>
        <span className="mono verdict-total">{total}</span>
        <span className="verdict-label">engines flagged malicious</span>
      </div>
      <div className="verdict-track" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="verdict-fill" style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
      </div>
    </div>
  )
}

export default function IOCLookup() {
  const [iocType, setIocType] = useState('ip')
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const typeMeta = IOC_TYPES.find(t => t.id === iocType)

  async function handleLookup() {
    const trimmed = value.trim()
    if (!trimmed) return

    setLoading(true)
    setResult(null)
    setError(null)

    try {
      const data = await lookupIOC(trimmed, iocType)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') handleLookup()
  }

  const tags = Array.isArray(result?.tags) ? result.tags : []

  return (
    <section className="ioc-lookup" aria-label="IOC threat intelligence lookup">

      <div className="ioc-header">
        <h1 className="ioc-title">IOC LOOKUP</h1>
        <p className="ioc-sub">
          Enrich an IP address, file hash, or domain using VirusTotal and AbuseIPDB.
          Results are cached for 6 hours.
        </p>
      </div>

      {/* Type selector */}
      <div className="ioc-type-row" role="group" aria-label="IOC type selector">
        {IOC_TYPES.map(t => (
          <button
            key={t.id}
            className={`ioc-type-btn${iocType === t.id ? ' active' : ''}`}
            onClick={() => { setIocType(t.id); setValue(''); setResult(null); setError(null) }}
            aria-label={`Look up ${t.label}`}
            aria-pressed={iocType === t.id}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Input bar */}
      <div className="ioc-input-row" role="search" aria-label="IOC value input">
        <span className="ioc-input-label" aria-hidden="true">{iocType.toUpperCase()} //</span>
        <input
          type="text"
          className="ioc-input"
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={typeMeta.placeholder}
          aria-label={`Enter ${typeMeta.label} to look up`}
          autoComplete="off"
          spellCheck="false"
        />
        <button
          className="ioc-submit-btn"
          onClick={handleLookup}
          disabled={loading || !value.trim()}
          aria-label="Run IOC lookup"
        >
          {loading ? 'LOOKING...' : 'LOOKUP'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="ioc-error" role="alert">
          <span className="ioc-error-icon" aria-hidden="true">!</span>
          Lookup failed: {error}
        </div>
      )}

      {/* Results */}
      {result && !error && (
        <div className="ioc-result" aria-label={`Results for ${result.value}`}>

          <div className="result-header">
            <span className="result-ioc-value mono" aria-label={`IOC value: ${result.value}`}>
              {result.value}
            </span>
            <span className="result-type-badge" aria-label={`Type: ${result.type}`}>
              {result.type?.toUpperCase()}
            </span>
            {result.cached && (
              <span className="result-cached-badge" aria-label="Result from cache">
                CACHED
              </span>
            )}
          </div>

          {result.error && (
            <div className="result-note" role="note">
              Note: {result.error}
            </div>
          )}

          <VerdictBar malicious={result.malicious_votes} total={result.total_votes} />

          <div className="result-grid">
            <ResultRow label="country"       value={result.country} />
            <ResultRow label="abuse score"   value={result.abuse_score != null ? `${result.abuse_score}%` : null} />
            <ResultRow label="last seen"     value={result.last_seen ? new Date(Number(result.last_seen) * 1000).toISOString().split('T')[0] : null} />
            <ResultRow label="vt report"     value={result.vt_link} />
          </div>

          {tags.length > 0 && (
            <div className="result-tags" aria-label={`Tags: ${tags.join(', ')}`}>
              {tags.map(tag => (
                <span key={tag} className="tag">{tag}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Empty state before lookup */}
      {!result && !error && !loading && (
        <div className="ioc-idle" aria-label="Enter an IOC value to begin">
          <div className="ioc-idle-diagram" aria-hidden="true">
            <span>IP</span>
            <span className="idle-arrow">--&gt;</span>
            <span>VEKTOR</span>
            <span className="idle-arrow">--&gt;</span>
            <span>VT + ABUSEIPDB</span>
          </div>
          <p>Enter an IP, hash, or domain above to check it against threat intelligence feeds.</p>
        </div>
      )}

    </section>
  )
}
