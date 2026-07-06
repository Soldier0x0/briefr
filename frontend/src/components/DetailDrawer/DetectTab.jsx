import { useState } from 'react'
import { copyToClipboard } from '../../utils/report.js'


// ── Detection Rule Engine UI ──────────────────────────────

function StatusBadge({ status }) {
  const s = (status || 'experimental').toLowerCase()
  const cls =
    s === 'stable' ? 'det-badge-stable'
    : s === 'test' ? 'det-badge-test'
    : 'det-badge-experimental'
  return <span className={`det-status-badge mono ${cls}`}>{s}</span>
}
function CopyButton({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false)
  async function handleCopy(e) {
    e.stopPropagation()
    const ok = await copyToClipboard(text)
    if (ok) {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }
  }
  return (
    <button type="button" className="det-copy-btn mono" onClick={handleCopy}>
      {copied ? 'Copied!' : label}
    </button>
  )
}
function downloadFile(content, filename) {
  const blob = new Blob([content], { type: 'text/yaml' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
function SigmaRuleCard({ rule }) {
  return (
    <div className="det-rule-card">
      <div className="det-rule-head">
        <div className="det-rule-meta">
          <StatusBadge status={rule.status} />
          <span className="det-rule-source mono">{rule.source}</span>
        </div>
        <div className="det-rule-actions">
          {rule.content && (
            <CopyButton text={rule.content} label="Copy" />
          )}
          <a
            className="det-rule-link mono"
            href={rule.html_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            View ↗
          </a>
          <a
            className="det-rule-download mono"
            href={rule.download_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Download
          </a>
        </div>
      </div>
      <p className="det-rule-title">{rule.title || rule.name || rule.path?.split('/').pop()}</p>
    </div>
  )
}
function ElasticRuleCard({ rule }) {
  return (
    <div className="det-rule-card">
      <div className="det-rule-head">
        <div className="det-rule-meta">
          <span className="det-status-badge mono det-badge-stable">elastic</span>
          <span className="det-rule-source mono">{rule.language || 'kuery'}</span>
        </div>
        <div className="det-rule-actions">
          <a
            className="det-rule-link mono"
            href={rule.html_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            View ↗
          </a>
          <a
            className="det-rule-download mono"
            href={rule.download_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Download
          </a>
        </div>
      </div>
      <p className="det-rule-title">{rule.name}</p>
    </div>
  )
}
function SiemBlock({ platform, label, data }) {
  const [open, setOpen] = useState(false)
  if (!data?.query) return null
  return (
    <div className="det-siem-block">
      <button
        type="button"
        className="det-siem-toggle mono"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <span className="det-siem-chevron">{open ? '▼' : '▶'}</span>
        {label}
      </button>
      {open && (
        <div className="det-siem-body">
          <div className="det-siem-query-wrap">
            <pre className="det-siem-query">{data.query}</pre>
            <CopyButton text={data.query} />
          </div>
          {data.notes && (
            <p className="det-siem-notes mono">{data.notes}</p>
          )}
        </div>
      )}
    </div>
  )
}
export default function TabDetect({ detection, loading, error, onRetry }) {
  if (loading) {
    return (
      <section className="drawer-section">
        <p className="drawer-intel-empty mono">// Loading detection intelligence…</p>
      </section>
    )
  }

  if (error) {
    return (
      <section className="drawer-section">
        <p className="drawer-intel-empty mono" role="alert">
          // Detection lookup failed: {error}
        </p>
        {onRetry && (
          <button type="button" className="drawer-risk-profile-cta-btn mono" onClick={onRetry}>
            Retry
          </button>
        )}
      </section>
    )
  }

  if (!detection) {
    return (
      <section className="drawer-section">
        <p className="drawer-intel-empty mono">
          // Open this tab to load detection rules and SIEM queries for this CVE
        </p>
      </section>
    )
  }

  const sigmaRules = detection.sigma_rules || []
  const elasticRules = detection.elastic_rules || []
  const hasCommunity = detection.has_community_rules
  const generatedSigma = detection.generated_sigma
  const siemQueries = detection.siem_queries || {}
  const logPatterns = siemQueries.log_patterns || []

  return (
    <>
      {/* Section 1: Community rules */}
      <section className="drawer-section" aria-labelledby="det-community-heading">
        <h3 id="det-community-heading" className="drawer-human-label mono">
          // EXISTING COMMUNITY RULES
        </h3>
        {!hasCommunity && (
          <p className="drawer-intel-empty mono">
            // No community rules found for this CVE — showing generated template below
          </p>
        )}
        {sigmaRules.map((r, i) => <SigmaRuleCard key={r.path || i} rule={r} />)}
        {elasticRules.map((r, i) => <ElasticRuleCard key={r.path || i} rule={r} />)}
      </section>

      {/* Section 2: Generated Sigma (only when no community rules) */}
      {!hasCommunity && generatedSigma && (
        <section className="drawer-section det-generated-section" aria-labelledby="det-generated-heading">
          <h3 id="det-generated-heading" className="drawer-human-label mono">
            // BRIEFR GENERATED RULE
          </h3>
          <div className="det-generated-meta">
            <span className="det-status-badge mono det-badge-experimental">experimental</span>
            <span className="det-confidence-badge mono">MEDIUM confidence</span>
          </div>
          <p className="det-generated-warning mono">
            ⚠ Experimental — validate field names and thresholds before deploying to production
          </p>
          <div className="det-code-wrap">
            <div className="det-code-actions">
              <CopyButton text={generatedSigma} label="Copy YAML" />
              <button
                type="button"
                className="det-copy-btn mono"
                onClick={() => downloadFile(generatedSigma, `briefr-${detection.cve_id.toLowerCase()}.yml`)}
              >
                Download .yml
              </button>
            </div>
            <pre className="det-code-block">{generatedSigma}</pre>
          </div>
        </section>
      )}

      {/* Section 3: SIEM Quick Search */}
      <section className="drawer-section" aria-labelledby="det-siem-heading">
        <h3 id="det-siem-heading" className="drawer-human-label mono">
          // SIEM QUICK SEARCH
          {siemQueries.title && (
            <span className="det-siem-technique-label"> · {siemQueries.title}</span>
          )}
        </h3>
        <div className="det-siem-list">
          <SiemBlock platform="elastic_kql" label="Elastic KQL" data={siemQueries.elastic_kql} />
          <SiemBlock platform="splunk_spl" label="Splunk SPL" data={siemQueries.splunk_spl} />
          <SiemBlock platform="sentinel_kql" label="Microsoft Sentinel KQL" data={siemQueries.sentinel_kql} />
          <SiemBlock platform="qradar_aql" label="QRadar AQL" data={siemQueries.qradar_aql} />
        </div>
      </section>

      {/* Section 4: Log Patterns */}
      {logPatterns.length > 0 && (
        <section className="drawer-section" aria-labelledby="det-logs-heading">
          <h3 id="det-logs-heading" className="drawer-human-label mono">
            // LOG PATTERNS
          </h3>
          <ul className="det-log-patterns" aria-label="Log patterns to look for">
            {logPatterns.map((p, i) => (
              <li key={i} className="det-log-pattern">{p}</li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
