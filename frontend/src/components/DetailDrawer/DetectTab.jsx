import { useState } from 'react'
import { copyToClipboard } from '../../utils/report.js'
import { notifyCopyFailure, notifyCopySuccess } from '../Toast.jsx'

import {
  confidenceMatchLabel,
  composeBasisLabel,
  composeBasisTooltip,
  formatEvidenceSummary,
} from '../../utils/detectLabels.js'
import ControlTooltip from '../ControlTooltip.jsx'
import IntelProvenanceLine from './IntelProvenanceLine.jsx'

const BASIS_LABELS = {
  attack_technique: 'ATT&CK technique',
  cwe: 'CWE class',
  generic: 'generic fallback',
}

const BASIS_TOOLTIPS = {
  attack_technique:
    'Hunt starter derived from a mapped MITRE ATT&CK technique template. Community Sigma/Elastic rules remain the primary deployable detections when present.',
  cwe:
    'Hunt starter derived from the CVE weakness class (CWE). Experimental — tune field names and keywords to your environment.',
  generic:
    'No ATT&CK technique or mapped CWE template matched — generic web-exploit keywords. High false-positive risk; validate before use.',
}

const EXPERIMENTAL_TOOLTIP =
  'BRIEFR-generated rules are experimental hunt starters, not production-ready detections. Validate field names, thresholds, and false positives in your environment before deployment.'

// ── Detection Rule Engine UI ──────────────────────────────

function StatusBadge({ status, title, children }) {
  const s = (status || 'experimental').toLowerCase()
  const cls =
    s === 'stable' ? 'det-badge-stable'
    : s === 'test' ? 'det-badge-test'
    : 'det-badge-experimental'
  return (
    <ControlTooltip text={title} trigger="hover-focus">
      <span className={`det-status-badge mono ${cls}`}>
        {children || s}
      </span>
    </ControlTooltip>
  )
}

function BasisBadge({ basis }) {
  const key = (basis || 'generic').toLowerCase()
  const label = BASIS_LABELS[key] || key
  const tip = BASIS_TOOLTIPS[key] || BASIS_TOOLTIPS.generic
  return (
    <ControlTooltip text={tip} trigger="hover-focus">
      <span className="det-basis-badge mono">
        Based on {label}
      </span>
    </ControlTooltip>
  )
}

function ComposeBasisBadge({ basis }) {
  if (!basis) return null
  return (
    <ControlTooltip text={composeBasisTooltip(basis)} trigger="hover-focus">
      <span className="det-compose-basis-badge mono">
        Evidence: {composeBasisLabel(basis)}
      </span>
    </ControlTooltip>
  )
}

function CopyButton({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false)
  async function handleCopy(e) {
    e.stopPropagation()
    const ok = await copyToClipboard(text)
    if (ok) {
      setCopied(true)
      notifyCopySuccess('Rule copied to clipboard')
      setTimeout(() => setCopied(false), 1500)
    } else {
      notifyCopyFailure()
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
          <StatusBadge status="stable">elastic</StatusBadge>
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

function GeneratedSigmaSection({
  detection,
  generatedSigma,
  meta,
  hasCommunity,
  detectionClass,
}) {
  const confidence = (meta?.briefr_confidence || 'MEDIUM').toUpperCase()
  const confidenceCls = confidence === 'LOW' ? 'det-confidence-low' : 'det-confidence-badge'
  const heading = hasCommunity
    ? '// BRIEFR HUNT STARTER · SUPPLEMENT'
    : '// BRIEFR HUNT STARTER'
  const supplementNote = hasCommunity
    ? 'Community rules above are primary — this generated template is an additional class-aware starting point.'
    : 'No community Sigma/Elastic rules were found — use this generated template as a starting point.'

  return (
    <section className="drawer-section det-generated-section" aria-labelledby="det-generated-heading">
      <h3 id="det-generated-heading" className="drawer-human-label mono">
        {heading}
      </h3>
      <p className="det-generated-intro mono">{supplementNote}</p>
      <div className="det-generated-meta">
        <StatusBadge status={meta?.status || 'experimental'} title={EXPERIMENTAL_TOOLTIP} />
        <BasisBadge basis={meta?.briefr_basis} />
        <ComposeBasisBadge basis={meta?.compose_basis} />
        <ControlTooltip text="BRIEFR confidence in this template match" trigger="hover-focus">
          <span className={`${confidenceCls} mono`}>
            {confidenceMatchLabel(confidence)}
          </span>
        </ControlTooltip>
        {(meta?.briefr_class || detectionClass) && (
          <ControlTooltip
            text="Detection pattern from the unified CWE/ATT&CK router (Sigma, SIEM, log patterns)"
            trigger="hover-focus"
          >
            <span className="det-class-badge mono">
              Pattern: {(meta?.briefr_class || detectionClass).replace(/_/g, ' ')}
            </span>
          </ControlTooltip>
        )}
      </div>
      <ControlTooltip text={EXPERIMENTAL_TOOLTIP} trigger="hover-focus">
        <p className="det-generated-warning mono">
          Experimental hunt starter — tune fields and test in your SIEM before production use.
        </p>
      </ControlTooltip>
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
          Could not load detection content. {error}
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
          Detection content is loading for this CVE.
        </p>
      </section>
    )
  }

  const sigmaRules = detection.sigma_rules || []
  const elasticRules = detection.elastic_rules || []
  const hasCommunity = detection.has_community_rules
  const generatedSigma = detection.generated_sigma
  const generatedMeta = detection.generated_sigma_meta || {}
  const siemQueries = detection.siem_queries || {}
  const logPatterns = siemQueries.log_patterns || []
  const detectionClass = siemQueries.detection_class || generatedMeta.briefr_class || ''
  const evidenceSummary = formatEvidenceSummary(detection.evidence)

  return (
    <>
      <IntelProvenanceLine provenance={detection.provenance} />

      <section className="drawer-section det-framing-section" aria-label="Detection framing">
        <p className="det-framing-note mono">
          Class-aware hunt starters — SIEM queries, log patterns, and a generated Sigma template
          keyed to this CVE&apos;s weakness class. Community rules stay primary when present.
        </p>
        {evidenceSummary && (
          <ControlTooltip
            text="Evidence pack from the detection composer (community rules, Nuclei artifacts, YARA). No LLM on this path."
            trigger="hover-focus"
          >
            <p className="det-evidence-summary mono" data-testid="det-evidence-summary">
              {evidenceSummary}
            </p>
          </ControlTooltip>
        )}
      </section>

      <section className="drawer-section" aria-labelledby="det-community-heading">
        <h3 id="det-community-heading" className="drawer-human-label drawer-tab-anchor mono">
          // EXISTING COMMUNITY RULES
        </h3>
        {!hasCommunity && (
          <p className="drawer-intel-empty mono">
            // No community Sigma/Elastic rules found for this CVE
          </p>
        )}
        {sigmaRules.map((r, i) => <SigmaRuleCard key={r.path || i} rule={r} />)}
        {elasticRules.map((r, i) => <ElasticRuleCard key={r.path || i} rule={r} />)}
      </section>

      {generatedSigma && (
        <GeneratedSigmaSection
          detection={detection}
          generatedSigma={generatedSigma}
          meta={generatedMeta}
          hasCommunity={hasCommunity}
          detectionClass={detectionClass}
        />
      )}

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
