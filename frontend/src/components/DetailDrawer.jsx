import { Component, useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchCVE,
  fetchCVECorrelation,
  fetchCVEDetection,
  fetchCVEEpssHistory,
  fetchCVEMomentum,
  fetchCVERelated,
  fetchCVERisk,
  fetchCVESentences,
  suppressCVECorrelation,
} from '../api.js'
import { buildSingleReport, copyToClipboard } from '../utils/report.js'
import { downloadSingleCvePdf } from '../utils/pdfReport.js'
import PdfExportModal from './PdfExportModal.jsx'
import { useInvestigationOptional } from '../context/InvestigationContext.jsx'
import { useAssetProfileOptional } from '../context/AssetProfileContext.jsx'
import {
  buildEpssSparklinePoints,
  epssSparklinePolyline,
  epssTrendLabel,
  EPSS_SPARKLINE_HEIGHT,
  EPSS_SPARKLINE_WIDTH,
  hasEnoughEpssHistory,
} from '../utils/epssSparkline.js'
import DrawerAtlasSection from './DrawerAtlasSection.jsx'
import { displayText } from '../utils/displayText.js'
import {
  buildRiskHeroSummary,
  componentBarColor,
  getRiskWeights,
  riskScoreColor,
  RISK_COMPONENT_LABELS,
} from '../scoring/riskScore.js'
import { profileToMatchAssets } from '../utils/assetProfileIo.js'
import { setMomentumScore } from '../utils/momentumCache.js'
import useModalLayer from '../hooks/useModalLayer.js'
import './DetailDrawer.css'


class DrawerTabErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error) {
    console.error('Drawer tab render failed:', error)
  }

  render() {
    if (this.state.error) {
      return (
        <p className="drawer-intel-empty mono">
          // This tab failed to render. Close and reopen the CVE, or refresh the page.
        </p>
      )
    }
    return this.props.children
  }
}


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
  return `https://attack.mitre.org/techniques/${clean}/`
}

function truncateText(text, maxLen) {
  const t = (text || '').trim()
  if (t.length <= maxLen) return t
  return `${t.slice(0, maxLen - 1)}…`
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

function drawerEpssBarColor(score) {
  if (score >= 0.5) return 'var(--red)'
  if (score >= 0.2) return 'var(--amber)'
  return 'var(--green)'
}

function EpssStaticBar({ score }) {
  const pct = Math.min(score * 100, 100)
  return (
    <div
      className="drawer-epss-static"
      aria-label={`EPSS exploitation probability: ${pct.toFixed(1)}%`}
    >
      <div
        className="drawer-epss-track"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="drawer-epss-fill"
          style={{ width: `${pct}%`, background: drawerEpssBarColor(score) }}
        />
      </div>
    </div>
  )
}

function EpssTrendSection({ cve, history, loading, epssSparklineRef }) {
  const score =
    typeof cve.epss_score === 'number' && cve.epss_score >= 0 ? cve.epss_score : null
  const points = buildEpssSparklinePoints(history, score)
  const polyline = epssSparklinePolyline(points)
  const trend = epssTrendLabel(history, score)
  const showSparkline = !loading && hasEnoughEpssHistory(points) && !!polyline
  const showStaticBar = !loading && score != null && !showSparkline

  if (score == null && !points.length && !loading) return null

  const pctLabel = score != null ? `${(score * 100).toFixed(1)}%` : '—'
  const trendLine = (
    <p className={`drawer-epss-trend-line mono drawer-epss-trend--${trend.tone}`}>
      {trend.label}
      {'  '}
      {pctLabel}
    </p>
  )

  return (
    <section className="drawer-section" aria-labelledby="epss-heading">
      <h3 id="epss-heading" className="drawer-section-label">EPSS</h3>
      {loading ? (
        <p className="drawer-epss-loading mono">// Loading EPSS trend…</p>
      ) : showSparkline ? (
        <>
          <svg
            ref={epssSparklineRef}
            className="drawer-epss-sparkline"
            width={EPSS_SPARKLINE_WIDTH}
            height={EPSS_SPARKLINE_HEIGHT}
            viewBox={`0 0 ${EPSS_SPARKLINE_WIDTH} ${EPSS_SPARKLINE_HEIGHT}`}
            role="img"
            aria-label={`EPSS score trend, last ${points.length} days`}
          >
            <polyline
              points={polyline}
              fill="none"
              stroke="var(--red)"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          {trendLine}
        </>
      ) : showStaticBar ? (
        <>
          <EpssStaticBar score={score} />
          {trendLine}
        </>
      ) : (
        <p className="drawer-epss-loading mono">// No EPSS history yet</p>
      )}
    </section>
  )
}

// ── Risk Score Breakdown ──────────────────────────────────

function RiskScoreBar({ score }) {
  const pct = Math.min(Math.max(score, 0), 1) * 100
  return (
    <div className="risk-bar-track" role="presentation">
      <div
        className="risk-bar-fill"
        style={{ width: `${pct}%`, background: componentBarColor(score) }}
      />
    </div>
  )
}

function RiskScoreBreakdown({ cve, riskScore, riskLoading, onOpenProfile, momentumData }) {
  if (riskLoading) {
    return (
      <section className="drawer-section drawer-risk-section" aria-labelledby="risk-score-heading">
        <h3 id="risk-score-heading" className="drawer-risk-section-label mono">
          // BRIEFR RISK SCORE
        </h3>
        <p className="drawer-risk-summary mono" style={{ color: 'var(--text3)' }}>
          Computing risk score…
        </p>
      </section>
    )
  }
  if (!riskScore || !cve) return null

  const { total, components, hasProfile } = riskScore
  const totalColor = riskScoreColor(total)
  const summary = buildRiskHeroSummary(cve, riskScore)

  // Fixed display order matching v1.1b weights
  const ORDERED_KEYS = ['asset', 'kev', 'epss', 'exploit', 'cvss', 'momentum']
  const breakdownRows = ORDERED_KEYS
    .filter(key => components[key] != null)
    .map(key => ({
      key,
      label: RISK_COMPONENT_LABELS[key] || key,
      ...components[key],
    }))

  const weights = riskScore.weights || getRiskWeights()
  const pointsSum = breakdownRows.reduce((sum, row) => sum + (row.points || 0), 0)
  const formulaParts = breakdownRows.map(row => row.points.toFixed(1))

  return (
    <section className="drawer-section drawer-risk-section" aria-labelledby="risk-score-heading">
      <h3 id="risk-score-heading" className="drawer-risk-section-label mono">
        // BRIEFR RISK SCORE
      </h3>

      <div className="drawer-risk-hero">
        <div
          className="drawer-risk-total"
          style={{ color: totalColor }}
          aria-label={
            !hasProfile
              ? `Risk score: ${total.toFixed(1)} out of 100. Asset exposure unknown until profile is loaded.`
              : `Risk score: ${total.toFixed(1)} out of 100`
          }
        >
          {total.toFixed(1)}
          {riskScore.momentumScore > 0.5 && (
            <span className="drawer-risk-momentum-arrow" aria-label="Rising threat momentum">↑</span>
          )}
        </div>
        {summary && (
          <p className="drawer-risk-summary mono">{summary}</p>
        )}
      </div>

      {!hasProfile && !cve.is_kev && onOpenProfile && (
        <div className="drawer-risk-profile-cta">
          <p className="drawer-risk-profile-cta-text mono">
            Load asset profile for personalised scoring
          </p>
          <button
            type="button"
            className="drawer-risk-profile-cta-btn mono"
            onClick={onOpenProfile}
          >
            Set up profile
          </button>
        </div>
      )}

      {!hasProfile && cve.is_kev && onOpenProfile && (
        <button
          type="button"
          className="drawer-risk-profile-link mono"
          onClick={onOpenProfile}
        >
          Personalise with asset profile
        </button>
      )}

      <div className="drawer-risk-components">
        {breakdownRows.map(row => (
          <div key={row.key} className="drawer-risk-component">
            <div className="drawer-risk-comp-header">
              <span className="drawer-risk-comp-label mono">{row.label}</span>
              <RiskScoreBar score={row.score} />
              <span className="drawer-risk-comp-points mono">
                {row.points.toFixed(1)} pts
              </span>
            </div>
            <p className="drawer-risk-comp-formula mono" aria-label={`${row.label} calculation`}>
              {row.score.toFixed(3)} × {(row.weight * 100).toFixed(0)}% × 100 = {row.points.toFixed(1)} pts
            </p>
            {row.key === 'momentum' && momentumData?.momentum_signals?.length > 0 ? (
              <ul className="drawer-risk-momentum-signals" aria-label="Momentum signals">
                {momentumData.momentum_signals.map((sig, i) => (
                  <li key={i} className="drawer-risk-momentum-signal mono">
                    {sig.description}
                    <span className="drawer-risk-momentum-contrib">
                      {sig.contribution > 0 ? ` (+${sig.contribution.toFixed(2)})` : ''}
                    </span>
                  </li>
                ))}
                <li className="drawer-risk-momentum-signal mono drawer-risk-momentum-total">
                  Momentum score = min(1.0, Σ signals) = {(momentumData.momentum_score ?? 0).toFixed(3)}
                </li>
              </ul>
            ) : row.sentence ? (
              <p className="drawer-risk-comp-sentence">{row.sentence}</p>
            ) : null}
          </div>
        ))}
      </div>
      <p className="drawer-risk-total-formula mono" aria-label="Risk score total calculation">
        {formulaParts.join(' + ')} = {pointsSum.toFixed(1)} → score {total.toFixed(1)} / 100
      </p>
      <p className="drawer-risk-weights mono">
        v1.1b weights from server — Asset {(weights.asset * 100).toFixed(0)}% · KEV {(weights.kev * 100).toFixed(0)}% · EPSS {(weights.epss * 100).toFixed(0)}% · Exploit {(weights.exploit * 100).toFixed(0)}% · CVSS {(weights.cvss * 100).toFixed(0)}% · Momentum {(weights.momentum * 100).toFixed(0)}%
      </p>
    </section>
  )
}

// ── Correlation Findings (Intel tab) ─────────────────────

function ConfidenceBadge({ confidence }) {
  const level = (confidence || 'low').toLowerCase()
  const cls =
    level === 'high'
      ? 'corr-badge-high'
      : level === 'medium'
        ? 'corr-badge-medium'
        : 'corr-badge-low'
  const title =
    level === 'high'
      ? 'Strong OTX or multi-IOC evidence'
      : level === 'medium'
        ? 'Moderate community or shared-pulse link'
        : 'Weak or IP-only signal — verify before acting'
  return (
    <span className={`corr-confidence-badge mono ${cls}`} title={title}>
      {level.toUpperCase()}
    </span>
  )
}

function CorrelationPriority({ priority }) {
  const score = priority?.score || 0
  const top = (priority?.components || [])[0]
  if (score <= 0 || !top) return null
  const level = score >= 50 ? 'high' : score >= 25 ? 'medium' : 'low'
  return (
    <div className={`corr-priority corr-priority-${level}`}>
      <span className="corr-priority-score mono">{score.toFixed(0)}</span>
      <p className="corr-priority-reason mono">{top.sentence}</p>
    </div>
  )
}

function CorrelationEvidence({ evidence }) {
  const items = Array.isArray(evidence) ? evidence : []
  if (!items.length) return null
  return (
    <details className="corr-evidence">
      <summary className="corr-evidence-toggle mono">Show evidence</summary>
      <ul className="corr-evidence-list">
        {items.map((ev, idx) => (
          <li key={`${ev.type}-${idx}`} className="mono corr-evidence-item">
            {ev.type === 'same_pulse' && `Same OTX pulse: ${ev.pulse_name || ev.pulse_id}`}
            {ev.type === 'shared_indicator' && (
              <>
                {`Shared ${ev.ioc_type}: ${ev.value}`}
                {ev.confirmation ? ` (${ev.confirmation})` : ''}
              </>
            )}
            {ev.type === 'enrichment_confirmation' && ev.summary}
            {!['same_pulse', 'shared_indicator', 'enrichment_confirmation'].includes(ev.type) && JSON.stringify(ev)}
          </li>
        ))}
      </ul>
    </details>
  )
}

function CorrelationFindings({ correlation, loading, onSelectCve, onDismiss }) {
  if (loading) {
    return (
      <section className="drawer-section" aria-labelledby="corr-heading">
        <h3 id="corr-heading" className="drawer-human-label mono">
          // CORRELATION FINDINGS
        </h3>
        <p className="drawer-intel-empty mono">// Loading correlation analysis…</p>
      </section>
    )
  }

  const campaigns = correlation?.campaigns || []
  const infra = correlation?.infrastructure || []
  const actor = correlation?.actor || []
  const temporal = correlation?.temporal || []
  const otxStatus = correlation?.otx_status
  const priority = correlation?.priority
  const hasFindings = campaigns.length > 0 || infra.length > 0 || actor.length > 0 || temporal.length > 0

  return (
    <section className="drawer-section" aria-labelledby="corr-heading">
      <h3 id="corr-heading" className="drawer-human-label mono">
        // CORRELATION FINDINGS
      </h3>

      <CorrelationPriority priority={priority} />

      {!hasFindings && otxStatus === 'not_configured' && (
        <p className="drawer-intel-empty mono">
          // Infrastructure correlation requires an OTX API key
        </p>
      )}

      {!hasFindings && otxStatus !== 'not_configured' && (
        <p className="drawer-intel-empty mono">
          // No correlation signals detected for this CVE
        </p>
      )}

      {campaigns.length > 0 && (
        <div className="corr-group" aria-label="Campaign correlation">
          <p className="corr-group-label mono">// CAMPAIGN LINKS</p>
          {campaigns.map(item => (
            <div key={item.campaign_id} className="corr-finding">
              <div className="corr-finding-head">
                <ConfidenceBadge confidence={item.confidence} />
                <p className="corr-finding-text">
                  <span className="corr-lane-tag mono">Campaign link</span>{' '}
                  {item.summary || item.label}
                  {item.attribution_conflict && (
                    <span className="corr-conflict-note" title="OTX adversary disagrees with MITRE actor mapping">
                      {' '}Attribution conflict — treat as unverified.
                    </span>
                  )}
                  {(item.members || []).filter(id => id !== correlation?.cve_id).map((cveId, idx) => (
                    <span key={cveId}>
                      {idx === 0 ? ' ' : ', '}
                      <button
                        type="button"
                        className="corr-cve-link mono"
                        onClick={() => onSelectCve?.(cveId)}
                        aria-label={`Open ${cveId} in drawer`}
                      >
                        {cveId}
                      </button>
                    </span>
                  ))}
                </p>
              </div>
              <CorrelationEvidence evidence={item.evidence} />
              {onDismiss && (
                <button
                  type="button"
                  className="corr-dismiss-btn mono"
                  onClick={() => onDismiss({ scope: 'campaign_id', key: { campaign_id: item.campaign_id } })}
                >
                  Not related
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Level 1: Infrastructure */}
      {infra.length > 0 && (
        <div className="corr-group" aria-label="Infrastructure correlation">
          <p className="corr-group-label mono">// SHARED INFRASTRUCTURE</p>
          {infra.map(item => (
            <div key={item.cve_id_b} className="corr-finding">
              <div className="corr-finding-head">
                <ConfidenceBadge confidence={item.confidence} />
                <p className="corr-finding-text">
                  <span className="corr-lane-tag mono">Shared infrastructure</span>{' '}
                  {item.summary ? (
                    (() => {
                      const peer = item.cve_id_b
                      const parts = item.summary.split(peer)
                      if (parts.length === 2) {
                        return (
                          <>
                            {parts[0]}
                            <button
                              type="button"
                              className="corr-cve-link mono"
                              onClick={() => onSelectCve?.(peer)}
                              aria-label={`Open ${peer} in drawer`}
                            >
                              {peer}
                            </button>
                            {parts[1]}
                          </>
                        )
                      }
                      return item.summary
                    })()
                  ) : (
                    <>
                      This CVE shares exploitation infrastructure with{' '}
                      <button
                        type="button"
                        className="corr-cve-link mono"
                        onClick={() => onSelectCve?.(item.cve_id_b)}
                        aria-label={`Open ${item.cve_id_b} in drawer`}
                      >
                        {item.cve_id_b}
                      </button>
                      {' '}({item.shared_ip_count ?? 0} common IP
                      {(item.shared_ip_count ?? 0) !== 1 ? 's' : ''}).
                    </>
                  )}
                </p>
              </div>
              <CorrelationEvidence evidence={item.evidence} />
              {onDismiss && (
                <button
                  type="button"
                  className="corr-dismiss-btn mono"
                  onClick={() => onDismiss({
                    scope: 'infrastructure',
                    key: { cve_id_b: item.cve_id_b },
                  })}
                >
                  Not related
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Level 2: Actor / Sector */}
      {actor.length > 0 && (
        <div className="corr-group" aria-label="Actor correlation">
          <p className="corr-group-label mono">// ACTOR ATTRIBUTION</p>
          {actor.map(item => (
            <div key={item.actor_name} className="corr-finding">
              <div className="corr-finding-head">
                <ConfidenceBadge confidence={item.confidence} />
                <p className="corr-finding-text">
                  <strong className="corr-actor-name">{item.actor_name}</strong>
                  {item.actor_sectors?.length > 0 && (
                    <>
                      {' '}exploits techniques used by this CVE.{' '}
                      {item.actor_name} has historically targeted{' '}
                      {item.actor_sectors.join(' and ')}.
                    </>
                  )}
                  {item.actor_sectors?.length === 0 && (
                    <> attributed to this CVE via threat intelligence.</>
                  )}
                  {item.user_sector_match && (
                    <span className="corr-sector-match">
                      {' '}Your declared sector — elevated risk.
                    </span>
                  )}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Level 3: Temporal */}
      {temporal.length > 0 && (
        <div className="corr-group" aria-label="Temporal anomaly">
          <p className="corr-group-label mono">// TEMPORAL ANOMALY</p>
          {temporal.map(item => (
            <div key={item.vendor} className="corr-finding">
              <div className="corr-finding-head">
                <ConfidenceBadge
                  confidence={item.anomaly_score >= 5 ? 'high' : item.anomaly_score >= 3 ? 'medium' : 'low'}
                />
                <p className="corr-finding-text">
                  <strong className="corr-actor-name" style={{ textTransform: 'capitalize' }}>
                    {item.vendor}
                  </strong>
                  {' '}{item.current_week_count} CVE{item.current_week_count !== 1 ? 's' : ''} published
                  this week — {(item.anomaly_score ?? 0).toFixed(1)}× the weekly average
                  ({(item.average_weekly_count ?? 0).toFixed(1)} normally).
                  Unusual volume may indicate coordinated research disclosure or active adversary focus.
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function TabOverview({ cve, riskScore, riskLoading, onOpenProfile, momentumData, products, cwes, urls, sentences, sentencesLoading, epssHistory, epssLoading, epssSparklineRef }) {
  return (
    <>
      <RiskScoreBreakdown cve={cve} riskScore={riskScore} riskLoading={riskLoading} onOpenProfile={onOpenProfile} momentumData={momentumData} />

      <EpssTrendSection
        cve={cve}
        history={epssHistory}
        loading={epssLoading}
        epssSparklineRef={epssSparklineRef}
      />

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

function exploitTypeLabel(type) {
  const t = (type || '').toLowerCase()
  if (t === 'metasploit') return 'Metasploit'
  if (t === 'weaponised' || t === 'weaponized') return 'Weaponised'
  return 'PoC'
}

function TabIntel({ techniques, publicExploits, greynoiseScans, otxPulses, otxConfigured, cve, loading, onInvestigateIp, onInvestigatePulse, pivotNotice, correlation, correlationLoading, onSelectCorrelatedCve, onDismissCorrelation }) {
  const exploits = Array.isArray(publicExploits) ? publicExploits : []
  const scans = Array.isArray(greynoiseScans) ? greynoiseScans : []
  const pulses = Array.isArray(otxPulses) ? otxPulses : []
  const techList = Array.isArray(techniques) ? techniques : []

  return (
    <>
      <section className="drawer-section" aria-labelledby="exploits-heading">
        <div className="drawer-intel-section-head">
          <h3 id="exploits-heading" className="drawer-human-label mono">
            // PUBLIC EXPLOITS
          </h3>
          <span className="drawer-count-badge mono" aria-label={`${exploits.length} exploits`}>
            {exploits.length}
          </span>
        </div>
        {loading && exploits.length === 0 ? (
          <p className="drawer-intel-empty mono">// Loading public exploit intelligence…</p>
        ) : exploits.length === 0 ? (
          <p className="drawer-intel-empty mono">// No public exploits from Sploitus or NVD references for this CVE</p>
        ) : (
          <ul className="drawer-exploit-list" aria-label="Public exploits from Sploitus">
            {exploits.map((exp, idx) => (
              <li key={exp.url || `${exp.title}-${idx}`} className="drawer-exploit-item">
                <div className="drawer-exploit-top">
                  <span
                    className={`drawer-exploit-type mono drawer-exploit-type--${(exp.type || 'poc').toLowerCase()}`}
                  >
                    {exploitTypeLabel(exp.type)}
                  </span>
                  {exp.source && (
                    <span className="drawer-exploit-source mono">{exp.source}</span>
                  )}
                  {exp.published_date && (
                    <span className="drawer-exploit-date mono">{exp.published_date}</span>
                  )}
                </div>
                <p className="drawer-exploit-title">{displayText(exp.title) || "Untitled exploit"}</p>
                {exp.url && (
                  <a
                    className="drawer-exploit-link mono"
                    href={exp.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View exploit &rarr;
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
        {exploits.some(exp => exp.requires_terms_acceptance) && (
          <p className="drawer-intel-hint mono">
            // Packet Storm links open in your browser and require a one-time Terms acceptance (once per session).
          </p>
        )}
      </section>

      <section className="drawer-section" aria-labelledby="scanning-heading">
        <h3 id="scanning-heading" className="drawer-human-label mono">// ACTIVE SCANNING</h3>
        {loading && scans.length === 0 ? (
          <p className="drawer-intel-empty mono">// Loading active scanning context…</p>
        ) : scans.length === 0 ? (
          <p className="drawer-intel-empty mono">
            // No exploitation-related IPs found in this CVE record
          </p>
        ) : (
          <ul className="drawer-gn-list" aria-label="GreyNoise scanning context">
            {scans.map(scan => {
              const cls = (scan.classification || 'unknown').toLowerCase()
              return (
                <li key={scan.ip} className="drawer-gn-item">
                  <div className="drawer-gn-top">
                    <span className="drawer-gn-ip mono">{scan.ip}</span>
                    <span className={`drawer-gn-class mono drawer-gn-class--${cls}`}>
                      {cls.toUpperCase()}
                    </span>
                  </div>
                  {scan.sentence && (
                    <p className="drawer-gn-sentence">{scan.sentence}</p>
                  )}
                  {scan.name && !scan.sentence && (
                    <p className="drawer-gn-name mono">{scan.name}</p>
                  )}
                  {scan.link && (
                    <a
                      className="drawer-exploit-link mono"
                      href={scan.link}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      GreyNoise viz &rarr;
                    </a>
                  )}
                  {onInvestigateIp && scan.ip && (
                    <button
                      type="button"
                      className="drawer-investigate-btn"
                      onClick={() => onInvestigateIp(scan.ip, cve)}
                    >
                      → Investigate
                    </button>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </section>


      <section className="drawer-section" aria-labelledby="campaigns-heading">
        <div className="drawer-intel-section-head">
          <h3 id="campaigns-heading" className="drawer-human-label mono">// ACTIVE CAMPAIGNS</h3>
          <span className="drawer-count-badge mono">{pulses.length}</span>
        </div>
        {otxConfigured === false ? (
          <p className="drawer-intel-empty mono">// Campaign intelligence unavailable — OTX not configured on this instance</p>
        ) : loading && pulses.length === 0 ? (
          <p className="drawer-intel-empty mono">// Loading campaign intelligence…</p>
        ) : pulses.length === 0 ? (
          <p className="drawer-intel-empty mono">// No community intelligence found for this CVE</p>
        ) : (
          <ul className="drawer-otx-list">
            {pulses.map((pulse, pulseIdx) => (
              <li key={pulse.pulse_id || `pulse-${pulseIdx}`} className="drawer-otx-item">
                <p className="drawer-otx-name">{displayText(pulse.pulse_name) || "Unnamed pulse"}</p>
                <div className="drawer-otx-meta">
                  {displayText(pulse.author) && (
                    <span className="drawer-otx-author mono">{displayText(pulse.author)}</span>
                  )}
                  {pulse.created_date && <span className="drawer-otx-date mono">{String(pulse.created_date).slice(0, 10)}</span>}
                  {pulse.ioc_count > 0 && <span className="drawer-otx-ioc-count mono">{pulse.ioc_count} IOCs</span>}
                </div>
                <div className="drawer-otx-tags">
                  {displayText(pulse.adversary) && (
                    <span className="drawer-otx-adversary mono">{displayText(pulse.adversary)}</span>
                  )}
                  {(pulse.malware_families || []).slice(0, 4).map((fam, famIdx) => {
                    const label = displayText(fam)
                    if (!label) return null
                    return <span key={`${label}-${famIdx}`} className="drawer-otx-malware mono">{label}</span>
                  })}
                </div>
                {onInvestigatePulse && pulse.pulse_id && (
                  <button type="button" className="drawer-investigate-btn" onClick={() => onInvestigatePulse(pulse, cve)}>→ Investigate IOCs</button>
                )}
              </li>
            ))}
          </ul>
        )}
        {pivotNotice && (
          <p className="drawer-intel-empty mono" role="status">{pivotNotice}</p>
        )}
      </section>

      <section className="drawer-section" aria-labelledby="mitre-heading">
        <h3 id="mitre-heading" className="drawer-section-label">MITRE ATT&CK</h3>
        {loading && techList.length === 0 ? (
          <p className="mitre-empty mono">// Loading ATT&CK mapping…</p>
        ) : techList.length === 0 ? (
          <p className="mitre-empty mono">// No ATT&CK mapping available</p>
        ) : (
          <div className="mitre-techniques" role="list" aria-label="Mapped ATT&CK techniques">
            {techList.map(tech => {
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

      <DrawerAtlasSection cve={cve} />

      <CorrelationFindings
        correlation={correlation}
        loading={correlationLoading}
        onSelectCve={onSelectCorrelatedCve}
        onDismiss={onDismissCorrelation}
      />
    </>
  )
}

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

function TabDetect({ detection, loading }) {
  if (loading) {
    return (
      <section className="drawer-section">
        <p className="drawer-intel-empty mono">// Loading detection intelligence…</p>
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

function TabRelated({ related, relatedMethod, loading, onSelectRelated }) {
  const semantic = relatedMethod === 'embeddings'
  if (loading) {
    return (
      <section className="drawer-section drawer-related-loading" aria-busy="true">
        <ul className="drawer-related-skeleton-list" aria-label="Loading related CVEs">
          {[0, 1, 2].map(i => (
            <li key={i} className="drawer-related-skeleton" aria-hidden="true" />
          ))}
        </ul>
      </section>
    )
  }

  if (!related.length) {
    return (
      <section className="drawer-section drawer-related-empty-wrap">
        <p className="drawer-related-empty mono">
          // No related CVEs found in the last 30 days for this product
        </p>
      </section>
    )
  }

  return (
    <section className="drawer-section" aria-labelledby="related-heading">
      <h3 id="related-heading" className="drawer-human-label mono">
        {semantic ? 'SIMILAR DESCRIPTION' : 'SAME PRODUCT FAMILY'}
      </h3>
      <p className="drawer-related-lane-note mono">
        {semantic
          ? '// Semantic neighbor — not the same as campaign correlation'
          : '// Same affected product — not the same as campaign correlation'}
      </p>
      <ul className="drawer-related-list" aria-label="Related CVEs">
        {related.map(item => {
          const sev = (item.severity || '').toUpperCase()
          const sevCol = severityColor(item.severity)
          return (
            <li key={item.cve_id}>
              <button
                type="button"
                className="drawer-related-item"
                onClick={() => onSelectRelated(item.cve_id)}
                aria-label={`Open ${item.cve_id}`}
              >
                <div className="drawer-related-top">
                  <span className="drawer-related-id mono">{item.cve_id}</span>
                  {sev && (
                    <span
                      className="drawer-related-sev mono"
                      style={{ color: sevCol, borderColor: sevCol }}
                    >
                      {sev}
                    </span>
                  )}
                  {item.cvss_score != null && (
                    <span className="drawer-related-cvss mono">
                      CVSS {Number(item.cvss_score).toFixed(1)}
                    </span>
                  )}
                  {semantic && item.similarity != null && (
                    <span className="drawer-related-sim mono">
                      {Math.round(Number(item.similarity) * 100)}% MATCH
                    </span>
                  )}
                </div>
                <p className="drawer-related-desc">
                  {truncateText(item.description, 90)}
                </p>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export default function DetailDrawer({ cve, loading = false, onClose, onCveReplace, watchlistState = null, onWatchlistChange }) {
  const [activeTab, setActiveTab] = useState('overview')
  const [reportOpen, setReportOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [sentences, setSentences] = useState(null)
  const [sentencesLoading, setSentencesLoading] = useState(false)
  const [epssHistory, setEpssHistory] = useState([])
  const [epssLoading, setEpssLoading] = useState(false)
  const [related, setRelated] = useState([])
  const [relatedMethod, setRelatedMethod] = useState('')
  const [relatedLoading, setRelatedLoading] = useState(false)
  const [correlation, setCorrelation] = useState(null)
  const [correlationLoading, setCorrelationLoading] = useState(false)
  const [detection, setDetection] = useState(null)
  const [detectionLoading, setDetectionLoading] = useState(false)
  const detectionFetchedRef = useRef(false)
  const [momentumData, setMomentumData] = useState(null)
  const [riskScore, setRiskScore] = useState(null)
  const [riskLoading, setRiskLoading] = useState(false)
  const [backStack, setBackStack] = useState([])
  const [pdfModalOpen, setPdfModalOpen] = useState(false)
  const [pdfBusy, setPdfBusy] = useState(false)
  const [pdfError, setPdfError] = useState(null)
  const reportRef = useRef(null)
  const epssSparklineRef = useRef(null)
  const sheetRef = useRef(null)
  const navigatingRef = useRef(false)
  const isOpen = !!cve

  // Trap Tab inside the drawer while open; restore focus to the originating
  // card on close. Escape stays owned by the global App handler.
  useModalLayer(isOpen, sheetRef)
  const investigation = useInvestigationOptional()
  const assetCtx = useAssetProfileOptional()

  useEffect(() => {
    if (!cve?.cve_id) {
      setRiskScore(null)
      setRiskLoading(false)
      return
    }
    let cancelled = false
    setRiskLoading(true)
    const payload =
      assetCtx?.isLoaded && assetCtx?.profile
        ? {
            profile: assetCtx.profile,
            assets: profileToMatchAssets(assetCtx.profile),
          }
        : {}
    fetchCVERisk(cve.cve_id, payload)
      .then(data => {
        if (cancelled) return
        setRiskScore({
          total: data.total,
          components: data.components,
          hasProfile: data.hasProfile,
          assetMatchType: data.assetMatchType,
          momentumScore: data.momentumScore,
          weights: data.weights,
        })
      })
      .catch(() => {
        if (!cancelled) setRiskScore(null)
      })
      .finally(() => {
        if (!cancelled) setRiskLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [cve?.cve_id, assetCtx?.profile, assetCtx?.isLoaded])

  useEffect(() => {
    investigation?.clearPivotNotice?.()
  }, [cve?.cve_id, investigation])

  useEffect(() => {
    if (!cve?.cve_id) {
      setSentences(null)
      setSentencesLoading(false)
      setEpssHistory([])
      setEpssLoading(false)
      setRelated([])
      setRelatedMethod('')
      setRelatedLoading(false)
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
    if (!cve?.cve_id) {
      setEpssHistory([])
      setEpssLoading(false)
      return
    }
    let cancelled = false
    setEpssLoading(true)
    fetchCVEEpssHistory(cve.cve_id)
      .then(data => {
        if (!cancelled) setEpssHistory(Array.isArray(data) ? data : [])
      })
      .catch(() => {
        if (!cancelled) setEpssHistory([])
      })
      .finally(() => {
        if (!cancelled) setEpssLoading(false)
      })
    return () => { cancelled = true }
  }, [cve?.cve_id])

  useEffect(() => {
    if (!cve?.cve_id || activeTab !== 'related') return
    let cancelled = false
    setRelatedLoading(true)
    fetchCVERelated(cve.cve_id, 5)
      .then(data => {
        if (!cancelled) {
          setRelated(data.data || [])
          setRelatedMethod(data.meta?.method || '')
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRelated([])
          setRelatedMethod('')
        }
      })
      .finally(() => {
        if (!cancelled) setRelatedLoading(false)
      })
    return () => { cancelled = true }
  }, [cve?.cve_id, activeTab])

  useEffect(() => {
    if (!isOpen) {
      setBackStack([])
      return
    }
    if (navigatingRef.current) {
      navigatingRef.current = false
      return
    }
    setBackStack([])
  }, [cve?.cve_id, isOpen])

  // Reset detection + momentum when CVE changes
  useEffect(() => {
    setDetection(null)
    setDetectionLoading(false)
    detectionFetchedRef.current = false
    setMomentumData(null)
  }, [cve?.cve_id])

  // Momentum: fetch on drawer open (lazy, not on card render)
  useEffect(() => {
    if (!cve?.cve_id) return
    let cancelled = false
    fetchCVEMomentum(cve.cve_id)
      .then(data => {
        if (!cancelled) {
          setMomentumData(data)
          // Publish to momentumCache so CVECard arrows update reactively
          if (data && typeof data.momentum_score === 'number') {
            setMomentumScore(cve.cve_id, data.momentum_score)
          }
        }
      })
      .catch(() => { /* non-critical — momentum is optional */ })
    return () => { cancelled = true }
  }, [cve?.cve_id])

  // Detection: lazy-fetch when Detect tab first activated
  useEffect(() => {
    if (activeTab !== 'detect' || !cve?.cve_id || detectionFetchedRef.current) return
    detectionFetchedRef.current = true
    let cancelled = false
    setDetectionLoading(true)
    const product = cve.affected_products?.[0]?.split(':')?.[1] || ''
    fetchCVEDetection(cve.cve_id, product)
      .then(data => { if (!cancelled) setDetection(data) })
      .catch(() => { if (!cancelled) setDetection(null) })
      .finally(() => { if (!cancelled) setDetectionLoading(false) })
    return () => { cancelled = true }
  }, [activeTab, cve?.cve_id])

  async function handleDismissCorrelation(body) {
    if (!cve?.cve_id) return
    try {
      await suppressCVECorrelation(cve.cve_id, body)
      const sector = assetCtx?.profile?.environment?.industry || ''
      const data = await fetchCVECorrelation(cve.cve_id, sector)
      setCorrelation(data)
    } catch {
      /* dismiss is best-effort */
    }
  }

  // Correlation: fetch on drawer open (Level 1 + 2 on-demand, Level 3 pre-computed)
  useEffect(() => {
    if (!cve?.cve_id) {
      setCorrelation(null)
      setCorrelationLoading(false)
      return
    }
    let cancelled = false
    setCorrelation(null)
    setCorrelationLoading(true)
    const sector = assetCtx?.profile?.environment?.industry || ''
    fetchCVECorrelation(cve.cve_id, sector)
      .then(data => {
        if (!cancelled) setCorrelation(data)
      })
      .catch(() => {
        if (!cancelled) setCorrelation(null)
      })
      .finally(() => {
        if (!cancelled) setCorrelationLoading(false)
      })
    return () => { cancelled = true }
  }, [cve?.cve_id, assetCtx?.profile?.environment?.industry])

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

  function handleDownloadPdfClick() {
    setReportOpen(false)
    setPdfError(null)
    setPdfModalOpen(true)
  }

  async function handlePdfConfirm({ analystName }) {
    if (!cve) return
    setPdfBusy(true)
    setPdfError(null)
    try {
      await downloadSingleCvePdf(cve, {
        analystName,
        sparklineElement: epssSparklineRef.current,
      })
      setPdfModalOpen(false)
    } catch (err) {
      setPdfError(err?.message || 'PDF generation failed.')
    } finally {
      setPdfBusy(false)
    }
  }

  function handleBack() {
    if (!backStack.length || !onCveReplace) return
    navigatingRef.current = true
    const prev = backStack[backStack.length - 1]
    setBackStack(stack => stack.slice(0, -1))
    onCveReplace(prev)
    setActiveTab('related')
  }

  async function handleSelectRelated(cveId) {
    if (!cve || !onCveReplace) return
    navigatingRef.current = true
    setBackStack(stack => [...stack, cve])
    setActiveTab('overview')
    try {
      const full = await fetchCVE(cveId)
      onCveReplace(full)
    } catch {
      onCveReplace({ cve_id: cveId })
    }
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
  const canGoBack = backStack.length > 0
  const isPinned = watchlistState === 'pin'
  const hasPreviewContent = Boolean(cve.description || cve.summary)
  const showBlockingLoadingOverlay = loading && !hasPreviewContent

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
        ref={sheetRef}
        tabIndex={-1}
      >
        <div className="drawer-sheet-handle" aria-hidden="true" />

        <div className="drawer-chrome">
          <header className="drawer-header">
            <div className="drawer-header-left">
              {canGoBack && (
                <button
                  type="button"
                  className="drawer-back-btn mono"
                  onClick={handleBack}
                  aria-label="Back to previous CVE"
                >
                  ←
                </button>
              )}
              <span className="drawer-cve-id mono">{cve.cve_id}</span>
              {cve.severity && (
                <span
                  className="drawer-sev-badge mono"
                  style={{ color: sevColor, borderColor: sevColor }}
                >
                  {cve.severity}
                </span>
              )}
              {cve.kev_ransomware_use && (
                <span
                  className="drawer-ransomware-badge mono"
                  title="Known ransomware campaign use (CISA KEV)"
                  aria-label="Known ransomware campaign use"
                >
                  RANSOMWARE
                </span>
              )}
            </div>
            <div className="drawer-header-actions">
              {onWatchlistChange && (
                <button
                  type="button"
                  className={`drawer-inv-btn mono${isPinned ? ' drawer-inv-btn-active' : ''}`}
                  onClick={() => onWatchlistChange(cve.cve_id, 'pin')}
                  aria-pressed={isPinned}
                  aria-label={isPinned ? `Unpin ${cve.cve_id}` : `Pin ${cve.cve_id}`}
                >
                  {isPinned ? 'Unpin' : 'Pin'}
                </button>
              )}
              {investigation && (
                <>
                  <button
                    type="button"
                    className="drawer-inv-btn mono"
                    onClick={() => investigation.startInvestigation(cve)}
                    aria-label={`Add ${cve.cve_id} to investigation`}
                  >
                    {investigation.isCveInThread(cve.cve_id) ? 'In thread' : 'Investigate'}
                  </button>
                  <button
                    type="button"
                    className="drawer-inv-btn drawer-inv-btn-secondary mono"
                    onClick={() => investigation.pivotToIocFromCve(cve)}
                    aria-label={`Look up indicators from ${cve.cve_id}`}
                  >
                    Lookup IOC
                  </button>
                </>
              )}
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
                      onClick={handleDownloadPdfClick}
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

        <div className="drawer-body-wrap">
          {showBlockingLoadingOverlay && (
            <div className="drawer-loading-overlay" aria-live="polite" aria-busy="true">
              <div className="drawer-loading-bar" role="progressbar" aria-label="Loading CVE details" />
              <p className="drawer-loading-text mono">Loading CVE details…</p>
            </div>
          )}

        <div
          className="drawer-tab-panel"
          role="tabpanel"
          id={`drawer-panel-${activeTab}`}
          aria-labelledby={`drawer-tab-${activeTab}`}
        >
          {activeTab === 'overview' && (
            <TabOverview
              cve={cve}
              riskScore={riskScore}
              riskLoading={riskLoading}
              onOpenProfile={assetCtx?.openProfileFlow}
              momentumData={momentumData}
              products={products}
              cwes={cwes}
              urls={urls}
              sentences={sentences}
              sentencesLoading={sentencesLoading}
              epssHistory={epssHistory}
              epssLoading={epssLoading}
              epssSparklineRef={epssSparklineRef}
            />
          )}
          {activeTab === 'intel' && (
            <DrawerTabErrorBoundary>
            <TabIntel
              techniques={techniques}
              publicExploits={cve.public_exploits}
              greynoiseScans={cve.greynoise_scans}
              otxPulses={cve.otx_pulses}
              otxConfigured={cve.otx_configured}
              cve={cve}
              loading={loading}
              onInvestigateIp={
                investigation
                  ? (ip, cveCtx) => investigation.pivotToIoc(ip, {
                      type: 'cve',
                      id: cveCtx.cve_id,
                      title: cveCtx.cve_id,
                      description: (cveCtx.summary || '').slice(0, 80),
                    })
                  : undefined
              }
              onInvestigatePulse={investigation?.pivotToOtxPulse ? (pulse, cveCtx) => investigation.pivotToOtxPulse(pulse, cveCtx) : undefined}
              pivotNotice={investigation?.pivotNotice}
              correlation={correlation}
              correlationLoading={correlationLoading}
              onSelectCorrelatedCve={handleSelectRelated}
              onDismissCorrelation={handleDismissCorrelation}
            />
            </DrawerTabErrorBoundary>
          )}
          {activeTab === 'detect' && (
            <TabDetect detection={detection} loading={detectionLoading} />
          )}
          {activeTab === 'related' && (
            <TabRelated
              related={related}
              relatedMethod={relatedMethod}
              loading={relatedLoading}
              onSelectRelated={handleSelectRelated}
            />
          )}
        </div>
        </div>
      </aside>

      <PdfExportModal
        open={pdfModalOpen}
        title={`PDF report — ${cve.cve_id}`}
        busy={pdfBusy}
        error={pdfError}
        onConfirm={handlePdfConfirm}
        onCancel={() => {
          if (!pdfBusy) {
            setPdfModalOpen(false)
            setPdfError(null)
          }
        }}
      />
    </>
  )
}
