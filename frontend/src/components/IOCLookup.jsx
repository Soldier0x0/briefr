import { useState, useRef, useEffect, useCallback } from 'react'
import { lookupIOC, fetchIOCUsage } from '../api.js'
import { notifyApiError } from './Toast.jsx'
import { useInvestigationOptional } from '../context/InvestigationContext.jsx'
import { extractActorTags } from '../utils/investigationActors.js'
import { isValidDomain } from '../utils/domainValidation.js'
import './IOCLookup.css'

// ── Type detection ────────────────────────────────────────
const IPV4_RE     = /^(\d{1,3}\.){3}\d{1,3}$/
const HASH_RE     = /^[0-9a-fA-F]{32}$|^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$/

function extractDomain(val) {
  let v = val.trim()
  if (!v) return ''
  try {
    const bare = v.split('/')[0].split('?')[0].split('#')[0]
    if (v.includes('://') || v.startsWith('//')) {
      const url = v.includes('://') ? v : `https:${v}`
      v = new URL(url).hostname || bare
    } else if (bare.includes(':') && !bare.startsWith('[')) {
      v = new URL(`http://${bare}`).hostname || bare.split(':')[0]
    } else {
      v = bare
    }
  } catch {
    v = v.split('/')[0].split('?')[0].split('#')[0]
    if (v.includes(':') && !v.startsWith('[')) v = v.split(':')[0]
  }
  return v.replace(/\.$/, '').toLowerCase()
}

function normalizeIocValue(val, type) {
  const v = val.trim()
  if (!v) return v
  if (type === 'domain') return extractDomain(v)
  if (type === 'hash') return v.toLowerCase()
  return v
}

function detectType(val) {
  const v = val.trim()
  if (!v) return null
  if (IPV4_RE.test(v)) return 'ip'
  if (HASH_RE.test(v)) return 'hash'
  const domain = extractDomain(v)
  if (isValidDomain(domain)) return 'domain'
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

function abuseScoreColor(score) {
  if (score == null) return 'var(--text3)'
  if (score >= 75) return 'var(--red)'
  if (score >= 40) return 'var(--amber)'
  return 'var(--green)'
}

function enginePillClass(category) {
  if (category === 'malicious') return 'malicious'
  if (category === 'suspicious') return 'suspicious'
  if (category === 'harmless') return 'harmless'
  return 'undetected'
}

// ── Error message mapping ─────────────────────────────────
function parseError(err) {
  if (err.status === 0)   return 'Network error — is the backend running?'
  if (err.status === 403) return 'Invalid API key — check your .env file'
  if (err.status === 429) return 'Rate limit reached — try again in 60 seconds'
  if (err.status === 404) return 'Not found in threat databases'
  if (err.status === 422) return err.message || 'Invalid input — use a full hostname, not a filename or path'
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

function quotaBarColor(warning) {
  if (!warning) return 'var(--text2)'
  if (warning.includes('exceeded')) return 'var(--red)'
  if (warning.includes('near')) return 'var(--amber)'
  return 'var(--text2)'
}

function UsageMeter({ label, used, limit, percentUsed, warning }) {
  if (limit == null) {
    return (
      <div className="quota-meter quota-meter--unmetered">
        <div className="quota-meter-head">
          <span className="quota-meter-label">{label}</span>
          <span className="quota-meter-val mono">{used.toLocaleString()} today</span>
        </div>
        <p className="quota-meter-note mono">// no published daily cap · fair use</p>
      </div>
    )
  }

  const pct = Math.min(Math.max(percentUsed ?? 0, 0), 100)
  const fillColor = quotaBarColor(warning)

  return (
    <div className="quota-meter">
      <div className="quota-meter-head">
        <span className="quota-meter-label">{label}</span>
        <span className="quota-meter-val mono" style={{ color: fillColor }}>
          {used.toLocaleString()} / {limit.toLocaleString()}
        </span>
      </div>
      <div
        className="quota-track"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label}: ${Math.round(pct)}% of daily quota used`}
      >
        <div
          className="quota-fill"
          style={{ width: `${pct}%`, background: fillColor }}
        />
      </div>
    </div>
  )
}

function quotaChipFillClass(warning) {
  if (!warning) return ''
  if (warning.includes('exceeded')) return 'danger'
  if (warning.includes('near')) return 'warn'
  return ''
}

function quotaChipSummary(svc) {
  if (svc.this_week?.limit != null) {
    const u = svc.this_week.used ?? 0
    const l = svc.this_week.limit
    return `${u} / ${l} week`
  }
  if (svc.today?.limit != null) {
    const u = svc.today.used ?? 0
    const l = svc.today.limit
    return `${u} / ${l} today`
  }
  return `${svc.today?.used ?? 0} calls`
}

function quotaChipPercent(svc) {
  if (svc.this_week?.limit != null) return svc.this_week.percent_used ?? 0
  if (svc.today?.limit != null) return svc.today.percent_used ?? 0
  return null
}

function IOCQuotaPanel() {
  const [detailOpen, setDetailOpen] = useState(false)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchIOCUsage()
      .then(payload => {
        if (!cancelled) setData(payload)
      })
      .catch(err => {
        if (!cancelled) {
          setError(err.message || 'Could not load quota')
          setData(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const services = data?.services || []

  return (
    <div className="ioc-quota-wrap" role="region" aria-label="IOC API quota usage">
      <div className="ioc-quota-panel" id="ioc-quota-panel">
        <p className="ioc-quota-asof mono" style={{ marginBottom: 10 }}>
          // API QUOTA — BRIEFR calls from this server
          {!loading && data?.today_date_utc && (
            <> · UTC {data.today_date_utc}{data.as_of_utc ? ` ${data.as_of_utc.slice(11, 19)}` : ''}</>
          )}
        </p>

        {loading && (
          <p className="ioc-quota-loading mono">// Loading usage counters…</p>
        )}
        {error && (
          <p className="ioc-quota-error mono" role="alert">{error}</p>
        )}

        {!loading && !error && services.length > 0 && (
          <div className="ioc-quota-strip">
            {services.map(svc => {
              const pct = quotaChipPercent(svc)
              return (
                <div key={svc.service} className="ioc-quota-chip">
                  <span className="ioc-quota-chip-name mono">{svc.name}</span>
                  <span className="ioc-quota-chip-val mono">{quotaChipSummary(svc)}</span>
                  {pct != null && (
                    <div className="ioc-quota-chip-bar" aria-hidden="true">
                      <div
                        className={`ioc-quota-chip-fill ${quotaChipFillClass(svc.warning)}`}
                        style={{ width: `${Math.min(pct, 100)}%` }}
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        <button
          type="button"
          className="ioc-quota-toggle mono"
          onClick={() => setDetailOpen(o => !o)}
          aria-expanded={detailOpen}
        >
          <span className={`ioc-quota-chevron${detailOpen ? '' : ' collapsed'}`} aria-hidden="true">▾</span>
          {detailOpen ? 'Hide limits & notes' : 'Show limits & notes'}
        </button>

        {detailOpen && !loading && !error && services.length > 0 && (
          <div className="ioc-quota-detail" style={{ marginTop: 12 }}>
            {services.map(svc => (
              <div key={svc.service} className="quota-service-block">
                <div className="quota-service-title">
                  <span className="mono">{svc.name}</span>
                  {svc.rate_limit && (
                    <span className="quota-rate mono">{svc.rate_limit}</span>
                  )}
                </div>
                {svc.today?.limit != null && (
                  <UsageMeter
                    label="Today"
                    used={svc.today?.used ?? 0}
                    limit={svc.today?.limit}
                    percentUsed={svc.today?.percent_used}
                    warning={svc.warning}
                  />
                )}
                {svc.this_week?.limit != null && (
                  <UsageMeter
                    label="This week (UTC Mon–Sun)"
                    used={svc.this_week?.used ?? 0}
                    limit={svc.this_week?.limit}
                    percentUsed={svc.this_week?.percent_used}
                    warning={svc.warning}
                  />
                )}
                {svc.this_month?.limit != null && (
                  <UsageMeter
                    label="This month"
                    used={svc.this_month?.used ?? 0}
                    limit={svc.this_month?.limit}
                    percentUsed={svc.this_month?.percent_used}
                    warning={svc.warning}
                  />
                )}
                {svc.today?.limit == null && svc.this_week?.limit == null && (
                  <UsageMeter
                    label="Today"
                    used={svc.today?.used ?? 0}
                    limit={null}
                    percentUsed={null}
                    warning={svc.warning}
                  />
                )}
                {svc.notes && (
                  <p className="quota-service-note mono">{svc.notes}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function ScoreRing({ malicious, total, color }) {
  const pct = total > 0 ? Math.min((malicious / total) * 100, 100) : 0
  const r = 38
  const circ = 2 * Math.PI * r
  const offset = circ - (pct / 100) * circ

  return (
    <div className="ioc-score-ring" aria-hidden="true">
      <svg viewBox="0 0 88 88">
        <circle cx="44" cy="44" r={r} fill="none" stroke="var(--bg3)" strokeWidth="6" />
        <circle
          cx="44"
          cy="44"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <div className="ioc-score-ring-label">
        <span className="ioc-score-ring-num" style={{ color }}>{malicious}</span>
        <span className="ioc-score-ring-denom">/ {total || '—'}</span>
      </div>
    </div>
  )
}

function IPResultBody({ result, onViewActorTechniques, onOpenCve }) {
  const actorTags = extractActorTags(result.tags)
  const { label, color, pct } = verdictInfo(result.malicious_votes ?? 0, result.total_votes ?? 0)
  const abuse = result.abuseipdb || {}
  const abuseScore = result.abuse_score ?? abuse.abuse_score
  const engines = result.vt_engines || []
  const flagged = engines.filter(e => e.category === 'malicious' || e.category === 'suspicious')
  const gnClass = result.greynoise?.classification === 'malicious'
    ? 'malicious'
    : result.greynoise?.classification === 'benign' ? 'benign' : ''

  const heroLine = () => {
    if (total > 0 && pct >= 0.1) {
      return (
        <>
          <strong style={{ color }}>{result.malicious_votes}</strong> of{' '}
          <strong>{result.total_votes}</strong> security vendors flagged this IP as{' '}
          <strong style={{ color }}>{label}</strong>.
        </>
      )
    }
    if (abuseScore != null && abuseScore >= 75) {
      return (
        <>
          AbuseIPDB reports <strong style={{ color: abuseScoreColor(abuseScore) }}>{abuseScore}%</strong>{' '}
          confidence of abuse
          {abuse.total_reports != null && (
            <> ({abuse.total_reports.toLocaleString()} reports)</>
          )}.
        </>
      )
    }
    return <>Limited threat intelligence — check external links below.</>
  }

  const total = result.total_votes ?? 0

  return (
    <>
      {(result.sources_missing?.length > 0) && (
        <p className="ioc-sources-hint mono" role="status">
          // Missing API keys: {result.sources_missing.join(', ')} — add to backend/.env
        </p>
      )}

      <div className="ioc-results-hero">
        <ScoreRing
          malicious={result.malicious_votes ?? 0}
          total={total}
          color={color}
        />
        <div className="ioc-results-hero-text">
          <p className="ioc-results-hero-title">{heroLine()}</p>
          <ThreatBar malicious={result.malicious_votes ?? 0} total={total} />
          {result.greynoise?.classification && (
            <span className={`ioc-greynoise-chip ${gnClass}`}>
              GreyNoise: {result.greynoise.classification}
              {result.greynoise.name ? ` · ${result.greynoise.name}` : ''}
            </span>
          )}
        </div>
      </div>

      {abuseScore != null && (
        <div className="ioc-abuse-section">
          <div className="ioc-abuse-label">
            <span>ABUSE CONFIDENCE</span>
            <span className="ioc-abuse-score-num" style={{ color: abuseScoreColor(abuseScore) }}>
              {abuseScore}%
            </span>
          </div>
          <div className="ioc-abuse-track" role="progressbar" aria-valuenow={abuseScore} aria-valuemin={0} aria-valuemax={100}>
            <div
              className="ioc-abuse-fill"
              style={{ width: `${abuseScore}%`, background: abuseScoreColor(abuseScore) }}
            />
          </div>
        </div>
      )}

      <div className="ioc-meta-cards">
        <div className="ioc-meta-card">
          <h3 className="ioc-meta-card-title">// NETWORK</h3>
          <div className="ioc-meta-row">
            <span className="ioc-meta-key">ISP</span>
            <span className="ioc-meta-val">{abuse.isp || '—'}</span>
          </div>
          <div className="ioc-meta-row">
            <span className="ioc-meta-key">Usage</span>
            <span className="ioc-meta-val">{abuse.usage_type || '—'}</span>
          </div>
          <div className="ioc-meta-row">
            <span className="ioc-meta-key">Domain</span>
            <span className="ioc-meta-val">{abuse.domain || '—'}</span>
          </div>
          <div className="ioc-meta-row">
            <span className="ioc-meta-key">ASN</span>
            <span className="ioc-meta-val">
              {result.vt_network?.asn || '—'}
              {result.vt_network?.as_owner ? ` · ${result.vt_network.as_owner}` : ''}
            </span>
          </div>
        </div>
        <div className="ioc-meta-card">
          <h3 className="ioc-meta-card-title">// REPUTATION</h3>
          <div className="ioc-meta-row">
            <span className="ioc-meta-key">Country</span>
            <span className="ioc-meta-val">
              {abuse.country_name || result.country || '—'}
              {abuse.country_code ? ` (${abuse.country_code})` : ''}
            </span>
          </div>
          <div className="ioc-meta-row">
            <span className="ioc-meta-key">Reports</span>
            <span className="ioc-meta-val">
              {abuse.total_reports != null ? abuse.total_reports.toLocaleString() : '—'}
              {abuse.num_distinct_users != null ? ` from ${abuse.num_distinct_users} sources` : ''}
            </span>
          </div>
          <div className="ioc-meta-row">
            <span className="ioc-meta-key">Last reported</span>
            <span className="ioc-meta-val mono">
              {abuse.last_reported_at
                ? String(abuse.last_reported_at).replace('T', ' ').slice(0, 16)
                : '—'}
            </span>
          </div>
          <div className="ioc-meta-row">
            <span className="ioc-meta-key">Flags</span>
            <span className="ioc-meta-val">
              {abuse.is_tor ? 'Tor ' : ''}
              {abuse.is_whitelisted ? 'Whitelisted' : ''}
              {!abuse.is_tor && !abuse.is_whitelisted ? '—' : ''}
            </span>
          </div>
        </div>
      </div>

      {engines.length > 0 && (
        <div className="ioc-vt-engines">
          <h3 className="ioc-vt-engines-title">
            // VIRUSTOTAL — {flagged.length} flagged of {engines.length} engines
          </h3>
          <div className="ioc-engine-grid">
            {engines.map(eng => (
              <div
                key={eng.name}
                className={`ioc-engine-pill ${enginePillClass(eng.category)}`}
                title={eng.result || eng.category}
              >
                <span className="ioc-engine-name">{eng.name}</span>
                <span className="ioc-engine-verdict">
                  {eng.category === 'malicious' || eng.category === 'suspicious'
                    ? (eng.result || eng.category)
                    : eng.category}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="ioc-external-links">
        {result.vt_link && (
          <a className="action-btn action-btn-primary" href={result.vt_link} target="_blank" rel="noopener noreferrer">
            VirusTotal &rarr;
          </a>
        )}
        {result.abuseipdb_link && (
          <a className="action-btn" href={result.abuseipdb_link} target="_blank" rel="noopener noreferrer">
            AbuseIPDB &rarr;
          </a>
        )}
        {result.greynoise?.link && (
          <a className="action-btn" href={result.greynoise.link} target="_blank" rel="noopener noreferrer">
            GreyNoise &rarr;
          </a>
        )}
      </div>

      {result.greynoise_sentence && (
        <EnrichmentBlock heading="// GREYNOISE" sentence={result.greynoise_sentence}>
          {result.greynoise?.link && (
            <a className="ioc-enrichment-link mono" href={result.greynoise.link} target="_blank" rel="noopener noreferrer">
              View on GreyNoise &rarr;
            </a>
          )}
        </EnrichmentBlock>
      )}

      <OtxEnrichment result={result} onOpenCve={onOpenCve} />

      {actorTags.length > 0 && (
        <section className="ioc-enrichment-block ioc-actor-tags" aria-label="Threat actor tags">
          <h3 className="ioc-enrichment-heading mono">// THREAT ACTOR TAGS</h3>
          <div className="ioc-actor-tag-row">
            {actorTags.map(tag => (
              <span key={tag} className="ioc-actor-tag mono">{tag}</span>
            ))}
          </div>
          {onViewActorTechniques && actorTags.map(tag => (
            <button
              key={`btn-${tag}`}
              type="button"
              className="ioc-pivot-btn"
              style={{ marginTop: 8 }}
              onClick={() => onViewActorTechniques(tag)}
            >
              → View Techniques ({tag})
            </button>
          ))}
        </section>
      )}
    </>
  )
}


function OtxEnrichment({ result, onOpenCve }) {
  if (!result?.otx_sentence && !result?.otx?.pulse_count) return null
  const otx = result.otx || {}
  const pulses = Array.isArray(otx.pulses) ? otx.pulses : []
  const cves = Array.isArray(otx.related_cves) ? otx.related_cves : []
  return (
    <EnrichmentBlock heading="// OTX" sentence={result.otx_sentence}>
      {pulses.length > 0 && (
        <ul className="ioc-otx-pulse-list">
          {pulses.slice(0, 6).map(p => (
            <li key={p.pulse_id || p.name} className="ioc-otx-pulse-item mono">
              {p.name}{p.adversary ? ` · ${p.adversary}` : ''}
            </li>
          ))}
        </ul>
      )}
      {cves.length > 0 && onOpenCve && (
        <div className="ioc-otx-cve-links">
          {cves.map(cveId => (
            <button key={cveId} type="button" className="ioc-otx-cve-link mono" onClick={() => onOpenCve(cveId)}>{cveId}</button>
          ))}
        </div>
      )}
    </EnrichmentBlock>
  )
}

function EnrichmentBlock({ heading, sentence, children }) {
  if (!sentence && !children) return null
  const headingId = `ioc-${heading.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`
  return (
    <section className="ioc-enrichment-block" aria-labelledby={headingId}>
      <h3 id={headingId} className="ioc-enrichment-heading mono">{heading}</h3>
      {sentence && <p className="ioc-enrichment-sentence">{sentence}</p>}
      {children}
    </section>
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
export default function IOCLookup({ prefill }) {
  const investigation = useInvestigationOptional()
  const [value, setValue]       = useState('')
  const [iocType, setIocType]   = useState('ip')
  const [detected, setDetected] = useState(null)
  const [loading, setLoading]   = useState(false)
  const [result, setResult]     = useState(null)
  const [error, setError]       = useState(null)
  const [copied, setCopied]     = useState(false)
  const [history, setHistory]   = useState([])   // session-only, no localStorage
  const [includeGreynoise, setIncludeGreynoise] = useState(false)

  const detectDebounce = useRef(null)
  const copiedTimerRef = useRef(null)

  useEffect(() => () => {
    if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current)
  }, [])
  const prefillHandled = useRef(null)
  const [indicatorQueue, setIndicatorQueue] = useState([])
  const [fromCveId, setFromCveId] = useState(null)
  const pivotFromRef = useRef(null)

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

  async function runLookup(lookupValue, lookupType, options = {}) {
    const raw = (lookupValue ?? value).trim()
    const type = lookupType ?? iocType
    if (!raw) return
    const trimmed = normalizeIocValue(raw, type)

    if (type === 'domain' && !isValidDomain(trimmed)) {
      setLoading(false)
      setResult(null)
      setError(
        `'${raw}' is not a valid domain. Paste a full hostname (e.g. plugins.trac.wordpress.org) or URL — filenames like class-query.php cannot be looked up.`,
      )
      return
    }

    setLoading(true)
    setResult(null)
    setError(null)

    try {
      const useGreynoise = type === 'ip' && (options.greynoise ?? includeGreynoise)
      const data = await lookupIOC(trimmed, type, { greynoise: useGreynoise })

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

      if (investigation?.isActive && !data.error) {
        investigation.recordIocPivot(trimmed, options.pivotFrom ?? pivotFromRef.current)
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
      notifyApiError(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!prefill?.trigger) return
    if (prefillHandled.current === prefill.trigger) return
    prefillHandled.current = prefill.trigger

    const indicators = Array.isArray(prefill.indicators) && prefill.indicators.length
      ? prefill.indicators
      : prefill.value
        ? [{ type: 'ip', value: prefill.value }]
        : []

    setFromCveId(prefill.fromCveId || null)
    pivotFromRef.current = prefill.pivotFrom || null
    setIndicatorQueue(indicators)

    const first = indicators[0]
    if (!first?.value) return

    setValue(first.value)
    const t = first.type === 'domain' ? 'domain' : first.type === 'hash' ? 'hash' : 'ip'
    setIocType(t)
    setDetected(t)
    // Analyst reviews chips first; prefill input only (no auto-lookup blast)
  }, [prefill?.trigger, prefill?.value, prefill?.indicators, prefill?.fromCveId, prefill?.pivotFrom])

  function selectQueuedIndicator(ind) {
    if (!ind?.value) return
    const t = ind.type === 'domain' ? 'domain' : ind.type === 'hash' ? 'hash' : 'ip'
    setValue(ind.value)
    setIocType(t)
    setDetected(t)
  }

  function clearLookup() {
    setValue('')
    setIocType('ip')
    setDetected(null)
    setResult(null)
    setError(null)
    setCopied(false)
    setIndicatorQueue([])
    setFromCveId(null)
    pivotFromRef.current = null
    prefillHandled.current = null
  }

  const hasLookupState = !!(
    value.trim() ||
    result ||
    error ||
    indicatorQueue.length ||
    fromCveId
  )

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
      result.abuseipdb?.isp ? `ISP:     ${result.abuseipdb.isp}` : null,
      result.abuseipdb?.total_reports != null
        ? `Reports: ${result.abuseipdb.total_reports}`
        : null,
      `Tags:    ${tags}`,
      result.vt_link    ? `Report:  ${result.vt_link}` : null,
      result.greynoise_sentence ? `GreyNoise: ${result.greynoise_sentence}` : null,
      result.malwarebazaar_sentence ? `MalwareBazaar: ${result.malwarebazaar_sentence}` : null,
      result.urlhaus_sentence ? `URLhaus: ${result.urlhaus_sentence}` : null,
      '',
      'Source: BRIEFR — VirusTotal, AbuseIPDB, GreyNoise, MalwareBazaar, URLhaus',
    ].filter(l => l !== null).join('\n')

    try {
      await navigator.clipboard.writeText(lines)
      setCopied(true)
      if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current)
      copiedTimerRef.current = setTimeout(() => setCopied(false), 2000)
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
          Check whether an IP, file hash, or domain appears in threat feeds. Paste a full URL or hostname — not filenames.
          GreyNoise is optional for IP lookups (50 calls/week).
        </p>
      </div>

      {fromCveId && (
        <div className="ioc-from-cve-banner mono" role="status">
          Indicators suggested from <span className="ioc-from-cve-id">{fromCveId}</span>
          — select a chip, then run LOOKUP when ready.
        </div>
      )}

      {indicatorQueue.length > 0 && (
        <div className="ioc-indicator-queue" role="group" aria-label="Suggested indicators">
          {indicatorQueue.map(ind => (
            <button
              key={`${ind.type}:${ind.value}`}
              type="button"
              className={`ioc-indicator-chip mono${value.trim() === ind.value ? ' selected' : ''}`}
              onClick={() => selectQueuedIndicator(ind)}
              aria-pressed={value.trim() === ind.value}
            >
              <span className="ioc-chip-type">{ind.type.toUpperCase()}</span>
              {ind.value}
            </button>
          ))}
        </div>
      )}

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
          placeholder="8.8.8.8  /  d41d8cd98f00b204e9800998ecf8427e  /  example.com or https://example.com/path"
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
          {iocType === 'ip' && (
            <label className="ioc-greynoise-opt mono">
              <input
                type="checkbox"
                checked={includeGreynoise}
                onChange={e => setIncludeGreynoise(e.target.checked)}
              />
              Include GreyNoise (uses weekly quota)
            </label>
          )}
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
          <button
            type="button"
            className="ioc-clear-btn mono"
            onClick={clearLookup}
            disabled={loading || !hasLookupState}
            aria-label="Clear IOC lookup input and results"
          >
            CLEAR
          </button>
        </div>

        <p className="ioc-privacy-notice mono" role="note">
          {'// Lookups are sent to third-party enrichment APIs (see Privacy Policy).'}<br />
          {'// Results cached locally (6h IOC, 1h GreyNoise). No user accounts.'}
        </p>

        <IOCQuotaPanel />
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

          {result.type === 'ip' ? (
            <IPResultBody
              result={result}
              onOpenCve={investigation?.openCveById}
              onViewActorTechniques={
                investigation
                  ? (actor) => investigation.pivotToAtlasActor(actor, {
                      type: 'ioc',
                      id: result.value,
                      title: result.value,
                    })
                  : undefined
              }
            />
          ) : (
            <>
              <ThreatBar
                malicious={result.malicious_votes ?? 0}
                total={result.total_votes ?? 0}
              />
              <DetailGrid result={result} />
            </>
          )}

          {result.type === 'ip' ? null : result.greynoise_sentence && (
            <EnrichmentBlock
              heading="// GREYNOISE"
              sentence={result.greynoise_sentence}
            >
              {result.greynoise?.link && (
                <a
                  className="ioc-enrichment-link mono"
                  href={result.greynoise.link}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  View on GreyNoise &rarr;
                </a>
              )}
            </EnrichmentBlock>
          )}

          {result.type === 'hash' && result.malwarebazaar?.malware_family && (
            <p className="ioc-malware-family mono" role="status">
              Malware family: <strong>{result.malwarebazaar.malware_family}</strong>
            </p>
          )}

          {result.type === 'hash' && result.malwarebazaar_sentence && (
            <EnrichmentBlock
              heading="// MALWAREBAZAAR"
              sentence={result.malwarebazaar_sentence}
            />
          )}

          {result.type === 'domain' && result.urlhaus_sentence && (
            <EnrichmentBlock
              heading="// URLHAUS"
              sentence={result.urlhaus_sentence}
            >
              {result.urlhaus?.reference && (
                <a
                  className="ioc-enrichment-link mono"
                  href={result.urlhaus.reference}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  URLhaus record &rarr;
                </a>
              )}
            </EnrichmentBlock>
          )}

          {result.type !== 'ip' && (<OtxEnrichment result={result} onOpenCve={investigation?.openCveById} />)}

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
            <span className="idle-node">VT</span>
            <span className="idle-arrow">+</span>
            <span className="idle-node">ABUSEIPDB</span>
            <span className="idle-arrow">+</span>
            <span className="idle-node">GREYNOISE</span>
            <span className="idle-arrow">+</span>
            <span className="idle-node">MALWAREBAZAAR</span>
            <span className="idle-arrow">+</span>
            <span className="idle-node">URLHAUS</span>
            <span className="idle-arrow">--&gt;</span>
            <span className="idle-node">VERDICT</span>
          </div>
          <p>Enter an IP, file hash, or domain above and press LOOKUP.</p>
        </div>
      )}

    </section>
  )
}
