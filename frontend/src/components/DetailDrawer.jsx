import { Component, useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchCVE,
  fetchCVEEpssHistory,
  fetchCVERelated,
  fetchCVESentences,
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
  calculateRiskScore,
  componentBarColor,
  riskScoreColor,
  RISK_COMPONENT_LABELS,
} from '../scoring/riskScore.js'
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

function Phase2Block({ title }) {
  const headingId = `phase2-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
  return (
    <section className="drawer-section" aria-labelledby={headingId}>
      <h3 id={headingId} className="drawer-section-label">{title}</h3>
      <p className="drawer-phase2 mono">// Coming in Phase 2</p>
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

function RiskScoreBreakdown({ cve, riskScore, onOpenProfile }) {
  if (!riskScore || !cve) return null

  const { total, components, hasProfile } = riskScore
  const totalColor = riskScoreColor(total)
  const summary = buildRiskHeroSummary(cve, riskScore)

  const breakdownRows = Object.entries(components)
    .filter(([key]) => hasProfile || key !== 'asset')
    .map(([key, comp]) => ({
      key,
      label: RISK_COMPONENT_LABELS[key] || key,
      ...comp,
    }))
    .sort((a, b) => b.points - a.points)

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
            {row.sentence && (
              <p className="drawer-risk-comp-sentence">{row.sentence}</p>
            )}
          </div>
        ))}
      </div>
      <p className="drawer-risk-weights mono">
        Weights: Asset 37% · KEV 26% · EPSS 16% · Exploit 11% · CVSS 10%
      </p>
    </section>
  )
}

function TabOverview({ cve, riskScore, onOpenProfile, products, cwes, urls, sentences, sentencesLoading, epssHistory, epssLoading, epssSparklineRef }) {
  return (
    <>
      <RiskScoreBreakdown cve={cve} riskScore={riskScore} onOpenProfile={onOpenProfile} />

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

function atlasTechniqueHref(tech) {
  if (tech?.url) return tech.url
  const id = tech?.technique_id || tech?.id
  if (!id) return null
  return `https://atlas.mitre.org/techniques/${String(id).toUpperCase()}/`
}

function TabAtlas({ cve, atlasTechniques, atlasCaseStudies }) {
  if (!cve?.has_ai_context) return null

  const techniques = Array.isArray(atlasTechniques) ? atlasTechniques : []
  const studies = Array.isArray(atlasCaseStudies) ? atlasCaseStudies : []
  const affectsDeclared = cveMatchesDeclaredAi(cve)

  return (
    <section className="drawer-section drawer-atlas-section" aria-labelledby="atlas-heading">
      <div className="drawer-atlas-head">
        <h3 id="atlas-heading" className="drawer-atlas-label mono">
          // AI/ML THREAT CONTEXT
        </h3>
        <a
          className="drawer-atlas-badge mono"
          href="https://atlas.mitre.org/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Powered by MITRE ATLAS
        </a>
      </div>

      {affectsDeclared && (
        <p className="drawer-atlas-profile-warn mono">
          This CVE may affect your declared AI/ML systems
        </p>
      )}

      {techniques.length === 0 ? (
        <p className="drawer-intel-empty mono">// No ATLAS techniques linked for this CVE</p>
      ) : (
        <div className="atlas-techniques" role="list" aria-label="Relevant ATLAS techniques">
          {techniques.map(tech => {
            const tid = tech.technique_id || tech.id
            const href = atlasTechniqueHref(tech)
            const desc = (tech.description || '').trim()
            const oneLine = desc.split(/\n/)[0]
            return (
              <article key={tid} className="atlas-technique-card" role="listitem">
                <div className="atlas-technique-top">
                  <span className="atlas-technique-id mono">{tid}</span>
                  {tech.tactic && (
                    <span className="atlas-tactic-badge mono">{tech.tactic}</span>
                  )}
                </div>
                <p className="atlas-technique-name">{tech.name}</p>
                {oneLine && (
                  <p className="atlas-technique-desc">{oneLine}</p>
                )}
                {href && (
                  <a
                    className="atlas-technique-link mono"
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    atlas.mitre.org &rarr;
                  </a>
                )}
              </article>
            )
          })}
        </div>
      )}

      {studies.length > 0 && (
        <div className="atlas-case-studies">
          <h4 className="drawer-atlas-subhead mono">// RELATED CASE STUDIES</h4>
          <ul className="atlas-case-list">
            {studies.map(study => (
              <li key={study.study_id} className="atlas-case-item">
                <p className="atlas-case-name">{study.name}</p>
                {study.summary && (
                  <p className="atlas-case-summary">{study.summary}</p>
                )}
                <p className="atlas-case-meta mono">
                  {study.target || 'AI system'}
                  {study.incident_date ? ` · ${study.incident_date}` : ''}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function TabIntel({ techniques, publicExploits, greynoiseScans, otxPulses, otxConfigured, cve, onInvestigateIp, onInvestigatePulse }) {
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
        {exploits.length === 0 ? (
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
        {scans.length === 0 ? (
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
          <p className="drawer-intel-empty mono">// OTX not configured — add OTX_API_KEY to backend .env and restart</p>
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
      </section>

      <section className="drawer-section" aria-labelledby="mitre-heading">
        <h3 id="mitre-heading" className="drawer-section-label">MITRE ATT&CK</h3>
        {techList.length === 0 ? (
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
    </>
  )
}

function TabDetect() {
  return (
    <>
      <Phase2Block title="LOG PATTERNS" />
      <Phase2Block title="SIEM QUERY SUGGESTIONS" />
      <Phase2Block title="YARA RULE AVAILABILITY" />
    </>
  )
}

function TabRelated({ related, loading, onSelectRelated }) {
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
      <h3 id="related-heading" className="drawer-human-label mono">SAME PRODUCT (30 DAYS)</h3>
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

export default function DetailDrawer({ cve, onClose, onCveReplace }) {
  const [activeTab, setActiveTab] = useState('overview')
  const [reportOpen, setReportOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [sentences, setSentences] = useState(null)
  const [sentencesLoading, setSentencesLoading] = useState(false)
  const [epssHistory, setEpssHistory] = useState([])
  const [epssLoading, setEpssLoading] = useState(false)
  const [related, setRelated] = useState([])
  const [relatedLoading, setRelatedLoading] = useState(false)
  const [backStack, setBackStack] = useState([])
  const [pdfModalOpen, setPdfModalOpen] = useState(false)
  const [pdfBusy, setPdfBusy] = useState(false)
  const reportRef = useRef(null)
  const epssSparklineRef = useRef(null)
  const navigatingRef = useRef(false)
  const isOpen = !!cve
  const investigation = useInvestigationOptional()
  const assetCtx = useAssetProfileOptional()

  const riskScore = useMemo(() => {
    if (!cve) return null
    const backendMatchScore = assetCtx?.isLoaded
      ? assetCtx.getMatchScore(cve.cve_id)
      : null
    return calculateRiskScore(cve, assetCtx?.profile ?? null, backendMatchScore)
  }, [cve, assetCtx?.profile, assetCtx?.isLoaded, assetCtx?.matchScores])

  useEffect(() => {
    if (!cve?.cve_id) {
      setSentences(null)
      setSentencesLoading(false)
      setEpssHistory([])
      setEpssLoading(false)
      setRelated([])
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
        if (!cancelled) setRelated(data.data || [])
      })
      .catch(() => {
        if (!cancelled) setRelated([])
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
    setPdfModalOpen(true)
  }

  async function handlePdfConfirm({ analystName }) {
    if (!cve) return
    setPdfBusy(true)
    try {
      await downloadSingleCvePdf(cve, {
        analystName,
        sparklineElement: epssSparklineRef.current,
      })
      setPdfModalOpen(false)
    } catch (err) {
      console.error('PDF generation failed:', err)
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
            </div>
            <div className="drawer-header-actions">
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
              onOpenProfile={assetCtx?.openProfileFlow}
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
            />
            </DrawerTabErrorBoundary>
          )}
          {activeTab === 'detect' && <TabDetect />}
          {activeTab === 'related' && (
            <TabRelated
              related={related}
              loading={relatedLoading}
              onSelectRelated={handleSelectRelated}
            />
          )}
        </div>
      </aside>

      <PdfExportModal
        open={pdfModalOpen}
        title={`PDF report — ${cve.cve_id}`}
        busy={pdfBusy}
        onConfirm={handlePdfConfirm}
        onCancel={() => !pdfBusy && setPdfModalOpen(false)}
      />
    </>
  )
}
