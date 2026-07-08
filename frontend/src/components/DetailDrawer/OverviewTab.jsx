import { useState } from 'react'
import {
  buildEpssSparklinePoints,
  epssSparklinePolyline,
  epssTrendLabel,
  EPSS_SPARKLINE_HEIGHT,
  EPSS_SPARKLINE_WIDTH,
  hasEnoughEpssHistory,
  hasMeaningfulEpssVariation,
} from '../../utils/epssSparkline.js'
import {
  buildRiskHeroSummary,
  componentBarColor,
  getAssetExposureStatus,
  getRiskWeights,
  riskScoreDisplayColor,
  RISK_COMPONENT_LABELS,
} from '../../scoring/riskScore.js'
import { patchStatusLabel, pickPrimaryRemediationReference } from '../../utils/patchReferences.js'
import { buildKevRemediationDisplay } from '../../utils/patchRemediation.js'
import { drawerEpssBarColor, capecHref, capecLabel, flattenOsvPackageRows } from './helpers.js'


function CriticalThreatSignals({ cve, riskScore, momentumData }) {
  if (!cve) return null
  const signals = []

  if (cve.is_kev) {
    signals.push({
      key: 'kev',
      label: 'CISA KEV',
      detail: 'Confirmed active exploitation — federal remediation catalogue',
      tone: 'critical',
    })
  }
  if (cve.kev_ransomware_use) {
    signals.push({
      key: 'ransomware',
      label: 'RANSOMWARE USE',
      detail: 'Known ransomware campaign association (CISA KEV)',
      tone: 'critical',
    })
  }

  const exploitScore = riskScore?.components?.exploit?.score ?? 0
  if (exploitScore >= 1.0) {
    signals.push({ key: 'msf', label: 'METASPLOIT', detail: 'Public Metasploit module available', tone: 'critical' })
  } else if (exploitScore >= 0.55) {
    signals.push({ key: 'poc', label: 'PUBLIC PoC', detail: 'Proof-of-concept exploit publicly available', tone: 'high' })
  } else if (cve.has_poc) {
    signals.push({ key: 'poc-ref', label: 'PoC REFERENCES', detail: 'Exploit references in public sources', tone: 'medium' })
  }

  const epss = typeof cve.epss_score === 'number' && cve.epss_score >= 0 ? cve.epss_score : null
  if (epss != null && epss >= 0.5) {
    signals.push({
      key: 'epss',
      label: 'HIGH EPSS',
      detail: `${(epss * 100).toFixed(1)}% exploitation probability (FIRST EPSS)`,
      tone: 'high',
    })
  }

  const mom = momentumData?.momentum_score ?? riskScore?.momentumScore ?? 0
  if (mom >= 0.5) {
    signals.push({
      key: 'momentum',
      label: 'RISING MOMENTUM',
      detail: 'Recent exploitation signals detected (EPSS trend, KEV recency, OTX)',
      tone: 'high',
    })
  }

  if (cve.cvss_score >= 9.0) {
    signals.push({
      key: 'cvss',
      label: `CVSS ${cve.cvss_score.toFixed(1)}`,
      detail: 'Critical technical severity rating',
      tone: 'high',
    })
  }

  if (!signals.length) return null

  return (
    <section className="drawer-section drawer-threat-signals" aria-labelledby="threat-signals-heading">
      <h3 id="threat-signals-heading" className="drawer-human-label mono">CRITICAL THREAT SIGNALS</h3>
      <ul className="drawer-threat-signal-list">
        {signals.map(sig => (
          <li key={sig.key} className={`drawer-threat-signal drawer-threat-signal--${sig.tone}`}>
            <span className="drawer-threat-signal-label mono">{sig.label}</span>
            <span className="drawer-threat-signal-detail">{sig.detail}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function PatchActionSection({ cve, sentences, urls }) {
  if (!cve) return null
  const status = patchStatusLabel(cve)
  const ref = pickPrimaryRemediationReference(cve, urls)
  const patchText = sentences?.patch
  const kevRemediation = buildKevRemediationDisplay({ cve, sentences })
  const showKevRemediation =
    kevRemediation &&
    (kevRemediation.variant === 'required-action' || !cve.patch_available)

  const statusClass =
    status === 'PATCH AVAILABLE' ? 'patch-available'
      : status === 'NO PATCH AVAILABLE' ? 'patch-unavailable'
        : 'patch-unknown'

  return (
    <section className="drawer-section drawer-patch-action" aria-labelledby="patch-action-heading">
      <h3 id="patch-action-heading" className="drawer-human-label mono">REMEDIATION</h3>
      <div className={`drawer-patch-status drawer-patch-status--${statusClass}`}>
        <span className="drawer-patch-status-label mono">{status}</span>
      </div>
      {patchText && (
        <p className="drawer-patch-guidance">{patchText}</p>
      )}
      {showKevRemediation && (
        <p className="drawer-patch-guidance drawer-patch-kev-guidance">
          <span className="mono drawer-patch-kev-tag">{kevRemediation.tag}</span>
          {' '}
          {kevRemediation.text}
        </p>
      )}
      {ref && (
        <a
          className="drawer-patch-ref-link mono"
          href={ref.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open {ref.label} →
        </a>
      )}
    </section>
  )
}

function RiskScoreHero({ cve, riskScore, riskLoading }) {
  if (riskLoading) {
    return (
      <section className="drawer-section drawer-risk-hero-section" aria-labelledby="risk-score-heading">
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

  const { total, hasProfile } = riskScore
  const totalColor = riskScoreDisplayColor(total, cve?.severity)
  const summary = buildRiskHeroSummary(cve, riskScore)

  return (
    <section className="drawer-section drawer-risk-hero-section" aria-labelledby="risk-score-heading">
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

const SSVC_LABELS = [
  ['Exploitation', 'Evidence of exploitation in the wild or public PoC'],
  ['Automatable', 'Whether attackers can exploit at scale without per-target setup'],
  ['Technical Impact', 'Worst-case technical outcome if exploited'],
  ['Decision', 'CISA Coordinator SSVC outcome (Act / Attend / Track)'],
]

function SsvcSection({ ssvc }) {
  const decisions = ssvc?.decisions
  if (!decisions || typeof decisions !== 'object') return null
  const rows = SSVC_LABELS.map(([key, explain]) => {
    const value = decisions[key]
    if (!value) return null
    return (
      <div key={key} className="drawer-ssvc-row">
        <span className="drawer-ssvc-key mono" title={explain}>{key}</span>
        <span className="drawer-ssvc-value mono">{value}</span>
      </div>
    )
  }).filter(Boolean)
  if (!rows.length && !decisions.computed) return null
  return (
    <section className="drawer-section" aria-labelledby="ssvc-heading">
      <h3 id="ssvc-heading" className="drawer-human-label mono">CISA SSVC</h3>
      <p className="drawer-ssvc-hint mono">
        Stakeholder-Specific Vulnerability Categorization from CISA Vulnrichment — prioritization context, not a CVSS replacement.
      </p>
      <div className="drawer-ssvc-grid" aria-label="SSVC decision points">
        {rows}
        {decisions.computed && (
          <p className="drawer-ssvc-computed mono" title="Compact SSVC vector from CISA">
            {decisions.computed}
          </p>
        )}
      </div>
    </section>
  )
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
  const percentile =
    typeof cve.epss_percentile === 'number' && cve.epss_percentile >= 0
      ? cve.epss_percentile
      : null
  const points = buildEpssSparklinePoints(history, score)
  const polyline = epssSparklinePolyline(points)
  const trend = epssTrendLabel(history, score)
  const meaningfulTrend = hasMeaningfulEpssVariation(points)
  const showSparkline = !loading && hasEnoughEpssHistory(points) && !!polyline && meaningfulTrend
  const showStaticBar = !loading && score != null && (!showSparkline || !meaningfulTrend)

  if (score == null && !points.length && !loading) return null

  const pctLabel = score != null ? `${(score * 100).toFixed(1)}%` : '—'
  const percentileLabel =
    percentile != null
      ? `${(percentile * 100).toFixed(1)}th percentile`
      : null
  const trendLine = (
    <p className={`drawer-epss-trend-line mono drawer-epss-trend--${trend.tone}`}>
      {trend.label}
      {'  '}
      {pctLabel}
      {percentileLabel && (
        <span
          className="drawer-epss-percentile"
          title="EPSS percentile — share of scored CVEs with a lower exploitation probability today"
        >
          {' · '}
          {percentileLabel}
        </span>
      )}
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
function OsvPackagesSection({ osvPackages }) {
  const rows = flattenOsvPackageRows(osvPackages)
  if (!rows.length) return null

  return (
    <section className="drawer-section" aria-labelledby="osv-heading">
      <h3 id="osv-heading" className="drawer-human-label mono">AFFECTED PACKAGES (OSV)</h3>
      <p className="drawer-osv-hint mono">
        Ecosystems and version ranges from OSV.dev — fetched when this drawer opens, not stored locally.
      </p>
      <div className="drawer-osv-table-wrap">
        <table className="drawer-osv-table mono" aria-label="OSV affected packages">
          <thead>
            <tr>
              <th scope="col">Ecosystem</th>
              <th scope="col">Package</th>
              <th scope="col">Affected range</th>
              <th scope="col">Fixed in</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.key}>
                <td>{row.ecosystem}</td>
                <td>{row.name}</td>
                <td>{row.range}</td>
                <td>{row.fix || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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

function AssetExposureSection({ riskScore, onOpenProfile, cve }) {
  const status = getAssetExposureStatus(riskScore)
  if (!status) return null

  const tierClass = `drawer-asset-exposure--${status.tier.toLowerCase().replace(/_/g, '-')}`

  return (
    <section
      className={`drawer-asset-exposure ${tierClass}`}
      aria-labelledby="asset-exposure-heading"
    >
      <h4 id="asset-exposure-heading" className="drawer-asset-exposure-label mono">
        ASSET EXPOSURE
      </h4>
      <div className="drawer-asset-exposure-status">
        <span className="drawer-asset-exposure-tier mono" title={status.detail}>
          {status.label}
        </span>
        <span className="drawer-asset-exposure-headline mono">{status.headline}</span>
      </div>
      <p className="drawer-asset-exposure-detail">{status.detail}</p>
      {status.matchReason && status.tier !== 'NOT_LOADED' && (
        <p className="drawer-asset-exposure-reason mono" aria-label="Match reason">
          Match: {status.matchReason}
        </p>
      )}
      {status.formulaNote && (
        <p className="drawer-asset-exposure-formula mono" aria-label="Scoring placeholder note">
          {status.formulaNote}
        </p>
      )}
      {status.tier === 'NOT_LOADED' && onOpenProfile && (
        <button
          type="button"
          className="drawer-asset-exposure-cta mono"
          onClick={onOpenProfile}
        >
          Load asset profile
        </button>
      )}
      {status.tier === 'NOT_LOADED' && cve?.is_kev && (
        <p className="drawer-asset-exposure-kev-note mono">
          CISA KEV listing indicates federal remediation urgency regardless of your stack.
        </p>
      )}
    </section>
  )
}
function RiskScoreBreakdown({ cve, riskScore, riskLoading, momentumData }) {
  const [expanded, setExpanded] = useState(false)

  if (riskLoading || !riskScore || !cve) return null

  const { total, components, hasProfile } = riskScore
  const assetExposure = getAssetExposureStatus(riskScore)

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
    <section className="drawer-section drawer-risk-section drawer-risk-methodology" aria-labelledby="risk-methodology-heading">
      <div className="drawer-risk-heading-row">
        <h3 id="risk-methodology-heading" className="drawer-risk-section-label mono">
          // WHY THIS SCORE?
        </h3>
        <button
          type="button"
          className="drawer-risk-toggle mono"
          onClick={() => setExpanded(v => !v)}
          aria-expanded={expanded}
          aria-controls="risk-breakdown-details"
        >
          {expanded ? '▾ Hide breakdown' : '▸ Show breakdown'}
        </button>
      </div>
      <p className="drawer-risk-methodology-hint">
        BRIEFR Risk Score v1.1b — weighted additive model. Expand for factor signal strength and score contribution.
      </p>

      {expanded && (
        <div id="risk-breakdown-details">
          <p className="drawer-risk-signal-legend mono">
            Signal strength (0–1) · Contribution = signal × weight × 100
          </p>
          <div className="drawer-risk-components">
            {breakdownRows.map(row => {
              const isAssetWithoutProfile = row.key === 'asset' && !hasProfile
              const maxPts = row.weight * 100
              return (
                <div key={row.key} className="drawer-risk-component">
                  <div className="drawer-risk-comp-header drawer-risk-comp-header--semantics">
                    <span className="drawer-risk-comp-label mono">{row.label}</span>
                    <div className="drawer-risk-signal-col">
                      <span className="drawer-risk-signal-caption mono">Signal</span>
                      {isAssetWithoutProfile ? (
                        <span
                          className="drawer-risk-comp-unknown mono"
                          title="Asset signal unavailable until profile is loaded"
                        >
                          N/A
                        </span>
                      ) : (
                        <>
                          <RiskScoreBar score={row.score} />
                          <span className="drawer-risk-signal-value mono">{row.score.toFixed(3)}</span>
                        </>
                      )}
                    </div>
                    <span className="drawer-risk-comp-points mono" title="Weighted contribution to BRIEFR score">
                      {isAssetWithoutProfile
                        ? '—'
                        : `${row.points.toFixed(1)} / ${maxPts.toFixed(0)} pts`}
                    </span>
                  </div>
                  <p className="drawer-risk-comp-formula mono" aria-label={`${row.label} calculation`}>
                    {isAssetWithoutProfile
                      ? (assetExposure?.formulaNote || 'Neutral 0.5 placeholder — not exposure probability')
                      : `${row.score.toFixed(3)} × ${(row.weight * 100).toFixed(0)}% × 100 = ${row.points.toFixed(1)} pts`}
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
                  ) : isAssetWithoutProfile ? (
                    <p className="drawer-risk-comp-sentence">
                      Load an asset profile to calculate whether this CVE affects your environment.
                    </p>
                  ) : row.sentence ? (
                    <p className="drawer-risk-comp-sentence">{row.sentence}</p>
                  ) : null}
                </div>
              )
            })}
          </div>
          <p className="drawer-risk-total-formula mono" aria-label="Risk score total calculation">
            {formulaParts.join(' + ')} = {pointsSum.toFixed(1)} → score {total.toFixed(1)} / 100
            {!hasProfile && (
              <span className="drawer-risk-placeholder-note">
                {' '}(includes neutral asset placeholder — not exposure)
              </span>
            )}
          </p>
          <p className="drawer-risk-weights mono">
            v1.1b weights — Asset {(weights.asset * 100).toFixed(0)}% · KEV {(weights.kev * 100).toFixed(0)}% · EPSS {(weights.epss * 100).toFixed(0)}% · Exploit {(weights.exploit * 100).toFixed(0)}% · CVSS {(weights.cvss * 100).toFixed(0)}% · Momentum {(weights.momentum * 100).toFixed(0)}%
          </p>
        </div>
      )}
    </section>
  )
}
export default function TabOverview({ cve, riskScore, riskLoading, onOpenProfile, momentumData, products, cwes, capecIds = [], urls, sentences, sentencesLoading, epssHistory, epssLoading, epssSparklineRef }) {
  return (
    <>
      {/* 1. BRIEFR score */}
      <RiskScoreHero cve={cve} riskScore={riskScore} riskLoading={riskLoading} />

      {/* 2. Asset exposure */}
      {!riskLoading && riskScore && (
        <section className="drawer-section">
          <AssetExposureSection riskScore={riskScore} onOpenProfile={onOpenProfile} cve={cve} />
        </section>
      )}

      {/* 3. Critical threat signals */}
      <CriticalThreatSignals cve={cve} riskScore={riskScore} momentumData={momentumData} />

      {/* 4. Plain English / why this matters */}
      {cve.summary && (
        <section className="drawer-section" aria-labelledby="plain-heading">
          <h3 id="plain-heading" className="drawer-human-label mono">WHY THIS MATTERS</h3>
          <blockquote className="drawer-summary">{cve.summary}</blockquote>
        </section>
      )}

      {/* 5. Patch status and remediation */}
      <PatchActionSection cve={cve} sentences={sentences} urls={urls} />

      {/* 6. Risk assessment */}
      {sentencesLoading && (
        <section className="drawer-section">
          <p className="drawer-human-loading mono">// Loading intelligence summary...</p>
        </section>
      )}
      {sentences?.risk && <HumanSentence label="RISK ASSESSMENT" text={sentences.risk} />}

      {/* 7. Exploitation likelihood and momentum */}
      <EpssTrendSection
        cve={cve}
        history={epssHistory}
        loading={epssLoading}
        epssSparklineRef={epssSparklineRef}
      />
      {sentences?.exploit_likelihood && (
        <HumanSentence label="EXPLOIT LIKELIHOOD" text={sentences.exploit_likelihood} />
      )}
      {sentences?.public_exploits && (
        <HumanSentence label="PUBLIC EXPLOITS" text={sentences.public_exploits} />
      )}
      {sentences?.kev && cve.is_kev && (
        <HumanSentence label="CISA KEV STATUS" text={sentences.kev} />
      )}

      {/* 8. Description and technical intelligence */}
      {cve.description && (
        <section className="drawer-section" aria-labelledby="desc-heading">
          <h3 id="desc-heading" className="drawer-human-label mono">DESCRIPTION</h3>
          <p className="drawer-description">{cve.description}</p>
        </section>
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

      {capecIds.length > 0 && (
        <section className="drawer-section" aria-labelledby="capec-heading">
          <h3 id="capec-heading" className="drawer-human-label mono">ATTACK PATTERNS (CAPEC)</h3>
          <p className="drawer-capec-hint mono">
            Common attack patterns linked to this CVE via CIRCL enrichment — not the same as CWE weakness types.
          </p>
          <div className="capec-list" aria-label="CAPEC attack patterns">
            {capecIds.map(id => {
              const href = capecHref(id)
              const label = capecLabel(id)
              return href ? (
                <a
                  key={id}
                  className="capec-tag mono"
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={`${label} — MITRE Common Attack Pattern Enumeration and Classification (sourced from CIRCL)`}
                >
                  {label}
                </a>
              ) : (
                <span key={id} className="capec-tag mono" title="CAPEC attack pattern ID from CIRCL enrichment">
                  {label}
                </span>
              )
            })}
          </div>
        </section>
      )}

      <SsvcSection ssvc={cve.ssvc} />
      <OsvPackagesSection osvPackages={cve.osv_packages} />

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

      {/* 9. Detailed scoring methodology (collapsed by default) */}
      <RiskScoreBreakdown
        cve={cve}
        riskScore={riskScore}
        riskLoading={riskLoading}
        momentumData={momentumData}
      />
    </>
  )
}
