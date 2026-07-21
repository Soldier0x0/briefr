import { ingestLogUrl } from '../../utils/adminLinks.js'
import { extractActorTags } from '../../utils/investigationActors.js'
import { DOMAIN_TERM_TIPS } from '../../utils/domainTermTips.js'
import { formatSectionHeading } from '../../utils/sectionHeading.js'
import ControlTooltip from '../ControlTooltip.jsx'
import ExplainTip from '../ExplainTip.jsx'
import { abuseScoreColor, enginePillClass, verdictInfo } from './iocUtils.js'

// ── Sub-components ────────────────────────────────────────
export function ThreatBar({ malicious, total }) {
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

export function DetailGrid({ result }) {
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

export function IPResultBody({ result, onViewActorTechniques, onOpenCve }) {
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
          Some enrichment sources are not configured: {result.sources_missing.join(', ')}. Results may be partial.
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
            <span title="Community-reported abuse score for this IP, separate from VirusTotal">AbuseIPDB confidence</span>
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
          <h3 className="ioc-meta-card-title">{formatSectionHeading('// NETWORK')}</h3>
          <div className="ioc-meta-row">
            <ControlTooltip text={DOMAIN_TERM_TIPS.isp} trigger="hover-focus">
              <span className="ioc-meta-key">ISP</span>
            </ControlTooltip>
            <span className="ioc-meta-val">{abuse.isp || '—'}</span>
          </div>
          <div className="ioc-meta-row">
            <ControlTooltip text={DOMAIN_TERM_TIPS.usageType} trigger="hover-focus">
              <span className="ioc-meta-key">Usage</span>
            </ControlTooltip>
            <span className="ioc-meta-val">{abuse.usage_type || '—'}</span>
          </div>
          <div className="ioc-meta-row">
            <span className="ioc-meta-key">Domain</span>
            <span className="ioc-meta-val">{abuse.domain || '—'}</span>
          </div>
          <div className="ioc-meta-row">
            <ControlTooltip text={DOMAIN_TERM_TIPS.asn} trigger="hover-focus">
              <span className="ioc-meta-key">ASN</span>
            </ControlTooltip>
            <span className="ioc-meta-val">
              {result.vt_network?.asn || '—'}
              {result.vt_network?.as_owner ? ` · ${result.vt_network.as_owner}` : ''}
            </span>
          </div>
        </div>
        <div className="ioc-meta-card">
          <h3 className="ioc-meta-card-title">{formatSectionHeading('// REPUTATION')}</h3>
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
            {formatSectionHeading('// VIRUSTOTAL')} — {flagged.length} flagged of {engines.length} engines
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
        <EnrichmentBlock
          heading="// GREYNOISE"
          sentence={result.greynoise_sentence}
          tip={DOMAIN_TERM_TIPS.greynoise}
        >
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
          <h3 className="ioc-enrichment-heading mono">{formatSectionHeading('// THREAT ACTOR TAGS')}</h3>
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


export function OtxEnrichment({ result, onOpenCve }) {
  if (!result?.otx_sentence && !result?.otx?.pulse_count) return null
  const otx = result.otx || {}
  const pulses = Array.isArray(otx.pulses) ? otx.pulses : []
  const cves = Array.isArray(otx.related_cves) ? otx.related_cves : []
  return (
    <EnrichmentBlock heading="// OTX" sentence={result.otx_sentence} tip={DOMAIN_TERM_TIPS.otx}>
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

export function EnrichmentBlock({ heading, sentence, children, tip }) {
  if (!sentence && !children) return null
  const headingText = formatSectionHeading(heading)
  const headingId = `ioc-${headingText.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`
  return (
    <section className="ioc-enrichment-block" aria-labelledby={headingId}>
      <h3 id={headingId} className="ioc-enrichment-heading mono">
        {headingText}
        {tip ? <ExplainTip text={tip} label={`Explain ${headingText}`} /> : null}
      </h3>
      {sentence && <p className="ioc-enrichment-sentence">{sentence}</p>}
      {children}
    </section>
  )
}

export function ActionRow({ result, onCopy, copied, onSaveWatchlist, watchlistSaving, watchlistSaved }) {
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
      {onSaveWatchlist && (
        <button
          type="button"
          className="action-btn"
          onClick={onSaveWatchlist}
          disabled={watchlistSaving || watchlistSaved}
          title="Nightly job checks saved IOCs against local OTX and ThreatFox data on this server"
        >
          {watchlistSaved ? 'ON WATCHLIST ✓' : watchlistSaving ? 'SAVING…' : 'SAVE FOR NIGHTLY MATCH'}
        </button>
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

export function WatchlistPanel({ items, loading, error, errorRequestId, onRemove, removingId, onRerun, authed }) {
  if (!authed) {
    return (
      <div className="ioc-watchlist ioc-watchlist-anon">
        <h2 className="ioc-history-heading mono">{formatSectionHeading('// WATCHLIST')}</h2>
        <p className="ioc-watchlist-hint mono">Sign in to save IOCs for nightly retro-match against local OTX + ThreatFox feeds.</p>
      </div>
    )
  }
  if (loading && !items.length) {
    return (
      <div className="ioc-watchlist">
        <h2 className="ioc-history-heading mono">{formatSectionHeading('// WATCHLIST')}</h2>
        <p className="ioc-watchlist-hint mono">Loading saved IOCs…</p>
      </div>
    )
  }
  if (error) {
    return (
      <div className="ioc-watchlist">
        <h2 className="ioc-history-heading mono">{formatSectionHeading('// WATCHLIST')}</h2>
        <p className="ioc-watchlist-hint mono">
          // {error}
          {errorRequestId && (
            <>
              {' '}
              (<a href={ingestLogUrl({ level: 'ERROR', requestId: errorRequestId })}>
                ref: {errorRequestId}
              </a>)
            </>
          )}
        </p>
      </div>
    )
  }
  return (
    <div className="ioc-watchlist" aria-label="Saved IOC watchlist">
      <h2 className="ioc-history-heading mono">{`${formatSectionHeading('// WATCHLIST')} (${items.length})`}</h2>
      <p className="ioc-watchlist-hint mono" title="Nightly job matches saved IOCs against local OTX pulse IOCs and ThreatFox mirror — no per-IOC enrichment API calls.">
        Saved IOCs retro-match nightly against OTX + ThreatFox mirrors on this server.
      </p>
      {items.length === 0 ? (
        <p className="ioc-watchlist-empty mono">// No saved IOCs yet — run a lookup and choose Save to watchlist</p>
      ) : (
        <ul className="ioc-watchlist-list">
          {items.map(item => (
            <li key={item.id} className="ioc-watchlist-row">
              <button
                type="button"
                className="history-item ioc-watchlist-item"
                onClick={() => onRerun({ value: item.ioc_value, iocType: item.ioc_type, malicious: 0, total: 0 })}
                aria-label={`Re-run lookup for ${item.ioc_value}`}
              >
                <span className="history-value mono">{item.ioc_value}</span>
                <div className="history-badges">
                  <span className="history-type-badge mono">{item.ioc_type.toUpperCase()}</span>
                  {item.label && <span className="ioc-watchlist-label mono">{item.label}</span>}
                </div>
              </button>
              <button
                type="button"
                className="ioc-watchlist-remove mono"
                onClick={() => onRemove(item.id)}
                disabled={removingId === item.id}
                aria-label={`Remove ${item.ioc_value} from watchlist`}
              >
                {removingId === item.id ? '…' : 'REMOVE'}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function HistoryItem({ item, onRerun }) {
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

export function IdleLookupState() {
  return (
    <div className="ioc-idle" aria-label="Awaiting input">
      <div className="idle-flow mono">
        <span className="idle-node" aria-hidden="true">INDICATOR</span>
        <span className="idle-arrow" aria-hidden="true">--&gt;</span>
        <ControlTooltip text={DOMAIN_TERM_TIPS.vt} trigger="hover-focus">
          <span className="idle-node">VT</span>
        </ControlTooltip>
        <span className="idle-arrow" aria-hidden="true">+</span>
        <ControlTooltip text={DOMAIN_TERM_TIPS.abuseipdb} trigger="hover-focus">
          <span className="idle-node">ABUSEIPDB</span>
        </ControlTooltip>
        <span className="idle-arrow" aria-hidden="true">+</span>
        <ControlTooltip text={DOMAIN_TERM_TIPS.greynoise} trigger="hover-focus">
          <span className="idle-node">GREYNOISE</span>
        </ControlTooltip>
        <span className="idle-arrow" aria-hidden="true">+</span>
        <ControlTooltip text={DOMAIN_TERM_TIPS.malwarebazaar} trigger="hover-focus">
          <span className="idle-node">MALWAREBAZAAR</span>
        </ControlTooltip>
        <span className="idle-arrow" aria-hidden="true">+</span>
        <ControlTooltip text={DOMAIN_TERM_TIPS.urlhaus} trigger="hover-focus">
          <span className="idle-node">URLHAUS</span>
        </ControlTooltip>
        <span className="idle-arrow" aria-hidden="true">--&gt;</span>
        <span className="idle-node" aria-hidden="true">VERDICT</span>
      </div>
      <p>Enter an IP, file hash, or domain above and press LOOKUP.</p>
    </div>
  )
}
