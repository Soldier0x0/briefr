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
import {
  buildKevRemediationDisplay,
  buildVendorRemediationDisplay,
  pickCisaRemediationReference,
  pickVendorRemediationReference,
} from '../../utils/patchRemediation.js'
import { patchStatusLabel } from '../../utils/patchReferences.js'
import { buildReferenceRows } from '../../utils/referenceRows.js'
import { buildExploitationDisplay } from '../../utils/exploitationDisplay.js'
import { drawerEpssBarColor, capecHref, capecLabel, flattenOsvPackageRows } from './helpers.js'


function formatKevDueDate(dateStr) {
  if (!dateStr) return null
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  } catch {
    return String(dateStr).slice(0, 10)
  }
}

function CriticalThreatSignals({ cve, riskScore, momentumData }) {
  if (!cve) return null
  const signals = []

  if (cve.is_kev) {
    const due = formatKevDueDate(cve.kev_due_date)
    signals.push({
      key: 'kev',
      label: 'CISA KEV',
      state: 'CONFIRMED ACTIVE EXPLOITATION',
      meta: due ? `Remediation due: ${due}` : 'Federal remediation catalogue',
      tone: 'critical',
    })
  }
  if (cve.kev_ransomware_use) {
    signals.push({
      key: 'ransomware',
      label: 'RANSOMWARE USE',
      state: 'KNOWN CAMPAIGN USE',
      meta: 'Associated with ransomware activity (CISA KEV)',
      tone: 'critical',
    })
  }

  const exploitScore = riskScore?.components?.exploit?.score ?? 0
  if (exploitScore >= 1.0) {
    signals.push({
      key: 'msf',
      label: 'METASPLOIT',
      state: 'MODULE AVAILABLE',
      meta: 'Public Metasploit module',
      tone: 'critical',
    })
  } else if (exploitScore >= 0.55) {
    signals.push({
      key: 'poc',
      label: 'PUBLIC PoC',
      state: 'EXPLOIT AVAILABLE',
      meta: 'Proof-of-concept publicly available',
      tone: 'high',
    })
  } else if (cve.has_poc) {
    signals.push({
      key: 'poc-ref',
      label: 'PoC REFERENCES',
      state: 'REFERENCES FOUND',
      meta: 'Exploit references in public sources',
      tone: 'medium',
    })
  }

  const mom = momentumData?.momentum_score ?? riskScore?.momentumScore ?? 0
  if (mom >= 0.5) {
    signals.push({
      key: 'momentum',
      label: 'MOMENTUM',
      state: 'RISING',
      meta: 'Recent exploitation signals (EPSS, KEV, OTX)',
      tone: 'high',
    })
  }

  if (cve.cvss_score >= 9.0) {
    signals.push({
      key: 'cvss',
      label: `CVSS ${cve.cvss_score.toFixed(1)}`,
      state: 'CRITICAL',
      meta: 'Critical technical severity rating',
      tone: 'high',
    })
  } else if (cve.cvss_score >= 7.0) {
    signals.push({
      key: 'cvss-high',
      label: `CVSS ${cve.cvss_score.toFixed(1)}`,
      state: 'HIGH',
      meta: 'High technical severity rating',
      tone: 'medium',
    })
  }

  if (!signals.length) return null

  return (
    <section className="drawer-section drawer-threat-signals" aria-labelledby="threat-signals-heading">
      <h3 id="threat-signals-heading" className="drawer-human-label mono">CRITICAL THREAT SIGNALS</h3>
      <ul className="drawer-threat-signals-grid">
        {signals.map(sig => (
          <li key={sig.key} className={`drawer-threat-signal-card drawer-threat-signal-card--${sig.tone}`}>
            <span className="drawer-threat-signal-label mono">{sig.label}</span>
            <span className="drawer-threat-signal-state">{sig.state}</span>
            <span className="drawer-threat-signal-meta">{sig.meta}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function PatchActionSection({ cve, sentences, urls }) {
  if (!cve) return null
  const vendor = buildVendorRemediationDisplay({ cve, sentences })
  const kevRemediation = buildKevRemediationDisplay({ cve, sentences })
  const vendorRef = pickVendorRemediationReference(cve, urls)
  const cisaRef = pickCisaRemediationReference(cve, urls)

  if (!vendor && !kevRemediation) return null

  const statusClass =
    vendor?.status === 'PATCH AVAILABLE' ? 'patch-available'
      : vendor?.status === 'NO PATCH AVAILABLE' ? 'patch-unavailable'
        : 'patch-unknown'

  return (
    <section className="drawer-section drawer-patch-action" aria-labelledby="patch-action-heading">
      <h3 id="patch-action-heading" className="drawer-human-label mono">REMEDIATION</h3>

      {vendor && (
        <div className="drawer-patch-block">
          <div className={`drawer-patch-status drawer-patch-status--${statusClass}`}>
            <span className="drawer-patch-status-label mono">{vendor.status}</span>
          </div>
          <p className="drawer-patch-guidance">{vendor.text}</p>
          {vendorRef && (
            <a
              className="drawer-patch-ref-link mono"
              href={vendorRef.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open {vendorRef.label} →
            </a>
          )}
        </div>
      )}

      {kevRemediation && kevRemediation.variant === 'required-action' && (
        <div className="drawer-patch-block">
          <p className="drawer-patch-cisa-heading mono">CISA REQUIRED ACTION</p>
          <p className="drawer-patch-guidance">{kevRemediation.text}</p>
          {cisaRef && (
            <a
              className="drawer-patch-ref-link mono"
              href={cisaRef.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open {cisaRef.label} →
            </a>
          )}
        </div>
      )}
    </section>
  )
}

function ExploitationSection({ cve, riskScore, momentumData, sentences, epssHistory, epssLoading, epssSparklineRef }) {
  const display = buildExploitationDisplay({ cve, riskScore, momentumData, sentences })
  if (!display) return null

  const score =
    typeof cve.epss_score === 'number' && cve.epss_score >= 0 ? cve.epss_score : null
  const points = buildEpssSparklinePoints(epssHistory, score)
  const polyline = epssSparklinePolyline(points)
  const trend = epssTrendLabel(epssHistory, score)
  const meaningfulTrend = hasMeaningfulEpssVariation(points)
  const showSparkline = !epssLoading && hasEnoughEpssHistory(points) && !!polyline && meaningfulTrend
  const showStaticBar = !epssLoading && score != null && (!showSparkline || !meaningfulTrend)

  return (
    <section className="drawer-section" aria-labelledby="exploitation-heading">
      <h3 id="exploitation-heading" className="drawer-human-label mono">EXPLOITATION</h3>
      <div className="drawer-exploitation-block">
        {display.observed.map(row => (
          <div key={row.key} className="drawer-exploitation-row">
            <span className="drawer-exploitation-label mono">{row.label}</span>
            <span className="drawer-exploitation-state">{row.state}</span>
          </div>
        ))}

        {display.epss && (
          <div className="drawer-exploitation-row">
            <span className="drawer-exploitation-label mono">EPSS 30-DAY PROBABILITY</span>
            <span className="drawer-exploitation-state">
              {display.epss.pct} — {display.epss.tier}
            </span>
            {epssLoading ? (
              <p className="drawer-exploitation-detail mono">Loading EPSS trend…</p>
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
                <p className={`drawer-exploitation-detail mono drawer-epss-trend--${trend.tone}`}>
                  {trend.label}
                </p>
              </>
            ) : showStaticBar ? (
              <div
                className="drawer-epss-static"
                aria-label={`EPSS exploitation probability: ${display.epss.pct}`}
              >
                <div className="drawer-epss-track" role="presentation">
                  <div
                    className="drawer-epss-fill"
                    style={{
                      width: `${Math.min(score * 100, 100)}%`,
                      background: drawerEpssBarColor(score),
                    }}
                  />
                </div>
              </div>
            ) : null}
            <p className="drawer-exploitation-detail">
              EPSS estimates broad exploitation probability across all scored CVEs.
            </p>
          </div>
        )}

        {display.publicExploit && (
          <div className="drawer-exploitation-row">
            <span className="drawer-exploitation-label mono">PUBLIC EXPLOIT</span>
            <span className="drawer-exploitation-state">{display.publicExploit.state}</span>
            {display.publicExploit.detail && (
              <p className="drawer-exploitation-detail">{display.publicExploit.detail}</p>
            )}
          </div>
        )}

        {display.momentum && (
          <div className="drawer-exploitation-row">
            <span className="drawer-exploitation-label mono">MOMENTUM</span>
            <span className="drawer-exploitation-state">{display.momentum.state}</span>
            <p className="drawer-exploitation-detail">{display.momentum.detail}</p>
          </div>
        )}

        {display.publicExploitsText && (
          <p className="drawer-exploitation-detail">{display.publicExploitsText}</p>
        )}

        {cve.is_kev && display.epss && (
          <p className="drawer-exploitation-context">{display.contextNote}</p>
        )}
      </div>
    </section>
  )
}

function ReferencesSection({ urls, cve }) {
  const rows = buildReferenceRows(urls, { cveId: cve?.cve_id, isKev: !!cve?.is_kev })
  if (!rows.length) return null

  return (
    <section className="drawer-section" aria-labelledby="refs-heading">
      <h3 id="refs-heading" className="drawer-human-label mono">REFERENCES</h3>
      <ul className="drawer-ref-rows" aria-label="Source references">
        {rows.map(row => (
          <li key={row.url} className="drawer-ref-row">
            <span className="drawer-ref-vendor mono">{row.vendor}</span>
            <span className="drawer-ref-title" title={row.url}>{row.title}</span>
            <a
              className="drawer-ref-link mono"
              href={row.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Open ${row.vendor} reference: ${row.title}`}
            >
              OPEN ↗
            </a>
          </li>
        ))}
      </ul>
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
  const compact = status.tier === 'NOT_LOADED'

  return (
    <section
      className={`drawer-asset-exposure ${tierClass}${compact ? ' drawer-asset-exposure--compact' : ''}`}
      aria-labelledby="asset-exposure-heading"
    >
      <h4 id="asset-exposure-heading" className="drawer-asset-exposure-label mono">
        ASSET EXPOSURE
      </h4>
      <div className="drawer-asset-exposure-status">
        <span className="drawer-asset-exposure-tier mono">{status.label}</span>
        <span className="drawer-asset-exposure-headline mono">{status.headline}</span>
      </div>
      <p className="drawer-asset-exposure-detail">{status.detail}</p>
      {!compact && status.matchReason && (
        <p className="drawer-asset-exposure-reason mono" aria-label="Match reason">
          Match: {status.matchReason}
        </p>
      )}
      {compact && onOpenProfile && (
        <button
          type="button"
          className="drawer-asset-exposure-cta mono"
          onClick={onOpenProfile}
        >
          Load asset profile
        </button>
      )}
      {!compact && status.tier === 'NOT_LOADED' && onOpenProfile && (
        <button
          type="button"
          className="drawer-asset-exposure-cta mono"
          onClick={onOpenProfile}
        >
          Load asset profile
        </button>
      )}
    </section>
  )
}

function RiskScoreBreakdownDetails({ cve, riskScore, momentumData }) {
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
    <div id="risk-breakdown-details" className="drawer-risk-breakdown-inline">
      <p className="drawer-risk-methodology-hint">
        BRIEFR Risk Score v1.1b — weighted additive model. Signal strength and score contribution below.
      </p>
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
                  The score uses a neutral 0.5 asset placeholder until a profile is loaded — this is not organizational exposure probability.
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
  )
}

function RiskScoreHero({ cve, riskScore, riskLoading, momentumData }) {
  const [expanded, setExpanded] = useState(false)

  if (riskLoading) {
    return (
      <section className="drawer-section drawer-risk-hero-section" aria-labelledby="risk-score-heading">
        <h3 id="risk-score-heading" className="drawer-risk-section-label mono">
          // BRIEFR RISK SCORE
        </h3>
        <p className="drawer-risk-summary mono" style={{ color: 'var(--text-muted, var(--text3))' }}>
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

      <button
        type="button"
        className="drawer-risk-why-toggle mono"
        onClick={() => setExpanded(v => !v)}
        aria-expanded={expanded}
        aria-controls="risk-breakdown-details"
      >
        {expanded ? 'Why this score? ▾' : 'Why this score? ▸'}
      </button>

      {expanded && (
        <RiskScoreBreakdownDetails
          cve={cve}
          riskScore={riskScore}
          momentumData={momentumData}
        />
      )}
    </section>
  )
}

export default function TabOverview({
  cve,
  riskScore,
  riskLoading,
  onOpenProfile,
  momentumData,
  products,
  cwes,
  capecIds = [],
  urls,
  sentences,
  sentencesLoading,
  epssHistory,
  epssLoading,
  epssSparklineRef,
}) {
  return (
    <>
      <RiskScoreHero
        cve={cve}
        riskScore={riskScore}
        riskLoading={riskLoading}
        momentumData={momentumData}
      />

      {!riskLoading && riskScore && (
        <section className="drawer-section">
          <AssetExposureSection riskScore={riskScore} onOpenProfile={onOpenProfile} cve={cve} />
        </section>
      )}

      <CriticalThreatSignals cve={cve} riskScore={riskScore} momentumData={momentumData} />

      {cve.summary && (
        <section className="drawer-section" aria-labelledby="plain-heading">
          <h3 id="plain-heading" className="drawer-human-label mono">WHY THIS MATTERS</h3>
          <blockquote className="drawer-summary">{cve.summary}</blockquote>
        </section>
      )}

      <PatchActionSection cve={cve} sentences={sentences} urls={urls} />

      {sentencesLoading && (
        <section className="drawer-section">
          <p className="drawer-human-loading mono">// Loading intelligence summary...</p>
        </section>
      )}
      {sentences?.risk && <HumanSentence label="RISK ASSESSMENT" text={sentences.risk} />}

      <ExploitationSection
        cve={cve}
        riskScore={riskScore}
        momentumData={momentumData}
        sentences={sentences}
        epssHistory={epssHistory}
        epssLoading={epssLoading}
        epssSparklineRef={epssSparklineRef}
      />

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
      <ReferencesSection urls={urls} cve={cve} />
    </>
  )
}
