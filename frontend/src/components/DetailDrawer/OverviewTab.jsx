import {
  buildEpssSparklinePoints,
  epssSparklinePolyline,
  epssTrendLabel,
  EPSS_SPARKLINE_HEIGHT,
  EPSS_SPARKLINE_WIDTH,
  hasEnoughEpssHistory,
} from '../../utils/epssSparkline.js'
import {
  buildRiskHeroSummary,
  componentBarColor,
  getRiskWeights,
  riskScoreDisplayColor,
  RISK_COMPONENT_LABELS,
} from '../../scoring/riskScore.js'
import { drawerEpssBarColor, capecHref, capecLabel, flattenOsvPackageRows } from './helpers.js'


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
  const totalColor = riskScoreDisplayColor(total, cve?.severity)
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
export default function TabOverview({ cve, riskScore, riskLoading, onOpenProfile, momentumData, products, cwes, capecIds = [], urls, sentences, sentencesLoading, epssHistory, epssLoading, epssSparklineRef }) {
  return (
    <>
      <RiskScoreBreakdown cve={cve} riskScore={riskScore} riskLoading={riskLoading} onOpenProfile={onOpenProfile} momentumData={momentumData} />

      <EpssTrendSection
        cve={cve}
        history={epssHistory}
        loading={epssLoading}
        epssSparklineRef={epssSparklineRef}
      />

      <SsvcSection ssvc={cve.ssvc} />

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
    </>
  )
}
