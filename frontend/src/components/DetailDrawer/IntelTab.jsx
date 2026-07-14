import { useMemo, useState } from 'react'
import { displayText } from '../../utils/displayText.js'
import {
  buildConnectionPanel,
  confidenceBadgeClass,
  confidenceFactorReasons,
  correlationItemIsStale,
  formatEvidenceItem,
  linkStrengthLabel,
} from '../../utils/correlationPresentation.js'
import { formatSharedObservablesSummary } from '../../utils/sharedObservables.js'
import DrawerAtlasSection from '../DrawerAtlasSection.jsx'
import IntelProvenanceLine from './IntelProvenanceLine.jsx'
import { exploitTypeLabel, techniqueLink } from './helpers.js'

const GENERIC_EXPLOIT_TITLES = new Set([
  'Vendor or advisory reference',
  'Proof-of-concept published',
  'Untitled exploit',
])

function exploitDisplayTitle(exp) {
  const title = displayText(exp.title) || ''
  if (title && !GENERIC_EXPLOIT_TITLES.has(title)) return title
  if (exp.url) {
    try {
      return new URL(exp.url).hostname.replace(/^www\./, '')
    } catch {
      /* ignore */
    }
  }
  return title || 'Reference'
}


// ── Correlation Findings (Intel tab) ─────────────────────

function ConfidenceBadge({ confidence, stale = false }) {
  const level = (confidence || 'low').toLowerCase()
  const cls = confidenceBadgeClass(confidence, { stale })
  const title =
    stale
      ? 'Stale shared-indicator evidence — observation age exceeds type half-life'
      : level === 'high'
      ? 'Strong OTX or multi-IOC evidence'
      : level === 'medium'
        ? 'Moderate community or shared-pulse link'
        : 'Weak or IP-only signal — verify before acting'
  return (
    <span className={`corr-confidence-badge mono ${cls}`} title={title}>
      {linkStrengthLabel(confidence)}
    </span>
  )
}

function ConnectionEvidence({ item, cveId, onSelectCve }) {
  if (!item) return null

  if (item.cve_id_b && cveId) {
    const panel = buildConnectionPanel(item, cveId)
    if (!panel.primary && !panel.limitedConfidence && !panel.confidenceFactors.length) return null

    return (
      <details className="corr-evidence">
        <summary className="corr-view-connection-toggle mono">View connection</summary>
        <div className="corr-connection-panel">
          <p className="corr-connection-heading mono">{panel.title}</p>
          {panel.primary && (
            <>
              {panel.timeline && (
                <p className="corr-connection-timeline mono" title="Observation timeline for shared evidence">
                  {panel.timeline}
                </p>
              )}
              <p className="corr-connection-meta">{panel.primary.heading}</p>
              <p className="corr-connection-value mono">{panel.primary.value}</p>
              {panel.primary.lines.map(line => (
                <p key={line} className="corr-connection-meta">{line}</p>
              ))}
              {panel.primary.source && (
                <p className="corr-connection-meta">Source: {panel.primary.source}</p>
              )}
            </>
          )}
          <p className="corr-connection-meta">Link strength: {panel.linkStrength}</p>
          {panel.limitedConfidence && (
            <p className="corr-connection-limited">{panel.limitedConfidence}</p>
          )}
          {panel.confidenceFactors.length > 0 && (
            <ul className="corr-confidence-factors">
              {panel.confidenceFactors.map(reason => (
                <li key={reason} className="corr-connection-meta">{reason}</li>
              ))}
            </ul>
          )}
          {panel.relatedCve && onSelectCve && (
            <button
              type="button"
              className="corr-connection-open mono"
              onClick={() => onSelectCve(panel.relatedCve)}
            >
              Open related CVE
            </button>
          )}
        </div>
      </details>
    )
  }

  const evidence = Array.isArray(item.evidence) ? item.evidence : []
  const formatted = evidence.map(ev => formatEvidenceItem(ev)).filter(Boolean)
  if (!formatted.length) return null

  const primary = formatted[0]
  const factorReasons = confidenceFactorReasons(item.confidence_factors)
  return (
    <details className="corr-evidence">
      <summary className="corr-view-connection-toggle mono">View connection</summary>
      <div className="corr-connection-panel">
        <p className="corr-connection-meta">{primary.heading}</p>
        <p className="corr-connection-value mono">{primary.value}</p>
        {primary.lines.map(line => (
          <p key={line} className="corr-connection-meta">{line}</p>
        ))}
        {primary.source && (
          <p className="corr-connection-meta">Source: {primary.source}</p>
        )}
        <p className="corr-connection-meta">
          Link strength: {linkStrengthLabel(item.confidence)}
        </p>
        {factorReasons.length > 0 && (
          <ul className="corr-confidence-factors">
            {factorReasons.map(reason => (
              <li key={reason} className="corr-connection-meta">{reason}</li>
            ))}
          </ul>
        )}
      </div>
    </details>
  )
}

function CorrelationSuppressAction({ onRequestSuppress, body, peerCve, label = 'Mark unrelated' }) {
  if (!onRequestSuppress) return null
  return (
    <button
      type="button"
      className="corr-mark-unrelated-btn mono"
      onClick={() => onRequestSuppress(body, peerCve)}
      aria-label={`${label} — suppress this correlation relationship`}
    >
      {label}
    </button>
  )
}

function SuppressedCorrelationsPanel({ suppressions, onRestore, cveId }) {
  if (!suppressions?.length) return null

  return (
    <div className="corr-suppressed-panel" aria-label="Suppressed correlation relationships">
      <p className="corr-suppressed-title mono">SUPPRESSED RELATIONSHIPS</p>
      <ul className="corr-suppressed-list">
        {suppressions.map((row, idx) => {
          const peer = row.scope_key || 'link'
          const label =
            row.scope === 'campaign_id'
              ? `Campaign ${peer}`
              : row.scope === 'pulse_id'
                ? `Pulse ${peer}`
                : `Relationship to ${peer}`
          return (
            <li key={`${row.scope}-${peer}-${row.created_at || row.id || idx}`} className="corr-suppressed-item">
              <span>{label}</span>
              {row.reason && <span className="mono">({row.reason})</span>}
              {onRestore && (
                <button
                  type="button"
                  className="corr-restore-btn mono"
                  onClick={() => onRestore(row)}
                  aria-label={`Restore suppressed correlation for ${cveId}`}
                >
                  Restore
                </button>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
function CorrelationPriority({ priority }) {
  const score = priority?.score || 0
  const top = (priority?.components || [])[0]
  if (score <= 0 || !top) return null
  const level = score >= 50 ? 'high' : score >= 25 ? 'medium' : 'low'
  return (
    <div
      className={`corr-priority corr-priority-${level}`}
      title="BRIEFR's deterministic prioritization of relationship evidence. Separate from vulnerability severity."
    >
      <span className="corr-priority-label mono">Correlation strength</span>
      <span className="corr-priority-score mono">{score.toFixed(0)}</span>
      <p className="corr-priority-reason mono">{top.sentence}</p>
    </div>
  )
}
function CorrelationEvidence({ evidence, item, cveId, onSelectCve }) {
  if (item && cveId) {
    return <ConnectionEvidence item={item} cveId={cveId} onSelectCve={onSelectCve} />
  }
  return null
}

const INFRA_PREVIEW = 3

function InfrastructureList({ items, onSelectCve, onRequestSuppress, cveId }) {
  const [showAll, setShowAll] = useState(false)
  const visible = showAll ? items : items.slice(0, INFRA_PREVIEW)
  const hidden = Math.max(0, items.length - INFRA_PREVIEW)

  return (
    <>
      <p className="corr-infra-context">
        Other CVEs that share IPs, domains, or hashes in OTX pulses — suggestive, not proof of the same attacker.
      </p>
      <div className="corr-infra-table" role="table" aria-label="Related threat infrastructure">
        <div className="corr-infra-head mono" role="row">
          <span role="columnheader">Related CVE</span>
          <span role="columnheader" className="corr-infra-col-strength">Link strength</span>
          <span role="columnheader" className="corr-infra-col-observables">Shared observables</span>
          <span role="columnheader" className="corr-infra-col-actions"> </span>
        </div>
        {visible.map(item => (
          <div key={item.cve_id_b} className="corr-infra-row" role="row">
            <span className="corr-infra-peer" role="cell">
              <button
                type="button"
                className="corr-cve-link mono"
                onClick={() => onSelectCve?.(item.cve_id_b)}
                aria-label={`Open ${item.cve_id_b} in drawer`}
              >
                {item.cve_id_b}
              </button>
            </span>
            <span className="corr-infra-conf corr-infra-col-strength" role="cell">
              <ConfidenceBadge confidence={item.confidence} stale={correlationItemIsStale(item)} />
            </span>
            <span className="corr-infra-ips mono corr-infra-col-observables" role="cell">
              {formatSharedObservablesSummary(item)}
            </span>
            <span className="corr-infra-actions" role="cell">
              <ConnectionEvidence item={item} cveId={cveId} onSelectCve={onSelectCve} />
              <CorrelationSuppressAction
                onRequestSuppress={onRequestSuppress}
                body={{ scope: 'infrastructure', key: { cve_id_b: item.cve_id_b } }}
                peerCve={item.cve_id_b}
              />
            </span>
          </div>
        ))}
      </div>
      {hidden > 0 && !showAll && (
        <button
          type="button"
          className="corr-show-more-btn mono"
          onClick={() => setShowAll(true)}
          aria-label={`Show ${hidden} more related CVEs`}
        >
          + {hidden} more related CVE{hidden === 1 ? '' : 's'}
        </button>
      )}
    </>
  )
}

function CorrelationFindings({
  correlation,
  loading,
  onSelectCve,
  onRequestSuppress,
  suppressions,
  onRestoreSuppression,
  cve,
  onInvestigateCampaign,
}) {
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

      <IntelProvenanceLine provenance={correlation?.provenance} />

      <CorrelationPriority priority={priority} />

      {!hasFindings && otxStatus === 'not_configured' && (
        <p className="drawer-intel-empty mono">
          Campaign and infrastructure linking needs OTX intelligence — not configured on this server.
        </p>
      )}

      {!hasFindings && otxStatus !== 'not_configured' && (
        <p className="drawer-intel-empty mono">
          No correlation signals detected for this CVE in configured sources.
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
              <CorrelationEvidence item={item} cveId={correlation?.cve_id} onSelectCve={onSelectCve} />
              <div className="corr-finding-foot">
                {onInvestigateCampaign && (item.members || []).some(id => id && id !== correlation?.cve_id) && (
                  <button
                    type="button"
                    className="drawer-investigate-btn"
                    onClick={() => onInvestigateCampaign(item, cve)}
                  >
                    Add to investigation
                  </button>
                )}
                <CorrelationSuppressAction
                  onRequestSuppress={onRequestSuppress}
                  body={{ scope: 'campaign_id', key: { campaign_id: item.campaign_id } }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {infra.length > 0 && (
        <div className="corr-group" aria-label="Related threat infrastructure">
          <p className="corr-group-label mono">// SHARED INDICATOR LINKS</p>
          <InfrastructureList
            items={infra}
            onSelectCve={onSelectCve}
            onRequestSuppress={onRequestSuppress}
            cveId={correlation?.cve_id}
          />
        </div>
      )}

      <SuppressedCorrelationsPanel
        suppressions={suppressions}
        onRestore={onRestoreSuppression}
        cveId={correlation?.cve_id}
      />

      {/* Level 2: Actor / Sector — infra block replaced above */}
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
                      {' '}Matches your declared sector — verify relevance to your environment.
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
                  Unusual volume — may reflect disclosure timing, researcher attention, or campaign activity. Treat as a signal, not a verdict.
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
const CAMPAIGN_SOURCE_PREVIEW = 5

function groupPulsesByAuthor(pulses) {
  const groups = new Map()
  for (const pulse of pulses) {
    const author = displayText(pulse.author) || 'Unknown source'
    if (!groups.has(author)) groups.set(author, [])
    groups.get(author).push(pulse)
  }
  for (const items of groups.values()) {
    items.sort((a, b) => String(b.created_date || '').localeCompare(String(a.created_date || '')))
  }
  return Array.from(groups.entries()).sort((a, b) => b[1].length - a[1].length)
}
function CampaignPulseRow({ pulse, cve, onInvestigatePulse }) {
  return (
    <li className="drawer-otx-item drawer-otx-item-compact">
      <p className="drawer-otx-name">{displayText(pulse.pulse_name) || 'Unnamed pulse'}</p>
      <div className="drawer-otx-meta">
        {pulse.created_date && (
          <span className="drawer-otx-date mono">{String(pulse.created_date).slice(0, 10)}</span>
        )}
        {pulse.ioc_count > 0 && (
          <span className="drawer-otx-ioc-count mono">{pulse.ioc_count} IOCs</span>
        )}
      </div>
      <div className="drawer-otx-tags">
        {displayText(pulse.adversary) && (
          <span className="drawer-otx-adversary mono">{displayText(pulse.adversary)}</span>
        )}
        {(pulse.malware_families || []).slice(0, 3).map((fam, famIdx) => {
          const label = displayText(fam)
          if (!label) return null
          return <span key={`${label}-${famIdx}`} className="drawer-otx-malware mono">{label}</span>
        })}
        {(pulse.targeted_countries || []).filter(Boolean).slice(0, 3).map((cc, ccIdx) => (
          <span
            key={`${cc}-${ccIdx}`}
            className="drawer-otx-country mono"
            title={`${cc} — Country targeted in this OTX pulse (AlienVault OTX community intelligence)`}
          >
            {cc}
          </span>
        ))}
      </div>
      {onInvestigatePulse && pulse.pulse_id && (
        <button type="button" className="drawer-investigate-btn" onClick={() => onInvestigatePulse(pulse, cve)}>
          Add to investigation
        </button>
      )}
    </li>
  )
}
function CampaignPulseGroup({ author, items, cve, onInvestigatePulse, defaultOpen }) {
  // Freeze initial open state so parent re-renders (e.g. "show more sources")
  // do not reset manual expand/collapse — same pattern as Forge SavedPack.
  const [initialOpen] = useState(defaultOpen)

  return (
    <details className="drawer-otx-group" open={initialOpen || undefined}>
      <summary className="drawer-otx-group-summary">
        <span className="drawer-otx-group-author mono">{author}</span>
        <span className="drawer-otx-group-count mono">
          {items.length} pulse{items.length === 1 ? '' : 's'}
        </span>
      </summary>
      <ul className="drawer-otx-list drawer-otx-group-list">
        {items.map((pulse, pulseIdx) => (
          <CampaignPulseRow
            key={pulse.pulse_id || `${author}-${pulseIdx}`}
            pulse={pulse}
            cve={cve}
            onInvestigatePulse={onInvestigatePulse}
          />
        ))}
      </ul>
    </details>
  )
}
function CampaignPulseGroups({ pulses, cve, onInvestigatePulse }) {
  const [showAllSources, setShowAllSources] = useState(false)
  const groups = useMemo(() => groupPulsesByAuthor(pulses), [pulses])
  const visibleGroups = showAllSources ? groups : groups.slice(0, CAMPAIGN_SOURCE_PREVIEW)
  const hiddenSourceCount = Math.max(0, groups.length - CAMPAIGN_SOURCE_PREVIEW)

  return (
    <div className="drawer-otx-groups">
      {visibleGroups.map(([author, items]) => (
        <CampaignPulseGroup
          key={author}
          author={author}
          items={items}
          cve={cve}
          onInvestigatePulse={onInvestigatePulse}
          defaultOpen={items.length <= 2 || groups.length === 1}
        />
      ))}
      {hiddenSourceCount > 0 && !showAllSources && (
        <button
          type="button"
          className="drawer-otx-more-btn mono"
          onClick={() => setShowAllSources(true)}
          aria-label={`Show ${hiddenSourceCount} more campaign sources`}
        >
          + {hiddenSourceCount} more source{hiddenSourceCount === 1 ? '' : 's'}
        </button>
      )}
    </div>
  )
}
function GreynoiseQuotaLine({ quota }) {
  const week = quota?.this_week
  if (!week || week.limit == null) return null
  return (
    <p
      className="drawer-gn-quota mono"
      title="GreyNoise Community API — 50 lookups per week (shared with Visualizer)"
    >
      GreyNoise quota: {week.used}/{week.limit} this week
      {week.remaining != null ? ` · ${week.remaining} left` : ''}
    </p>
  )
}

export default function TabIntel({
  techniques,
  publicExploits,
  exploitProvenance,
  greynoiseConfigured,
  greynoiseScans,
  greynoiseLoading,
  greynoiseLoaded,
  greynoiseQuota,
  onLoadGreynoise,
  otxPulses,
  otxConfigured,
  cve,
  loading,
  onInvestigateIp,
  onInvestigatePulse,
  onInvestigateCampaign,
  pivotNotice,
  correlation,
  correlationLoading,
  onSelectCorrelatedCve,
  onRequestSuppressCorrelation,
  suppressions,
  onRestoreSuppression,
}) {
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
        <IntelProvenanceLine provenance={exploitProvenance} />
        {loading && exploits.length === 0 ? (
          <p className="drawer-intel-empty mono">// Loading public exploit intelligence…</p>
        ) : exploits.length === 0 ? (
          <p className="drawer-intel-empty mono">// No public exploits from Sploitus or NVD references for this CVE</p>
        ) : (
          <div className="drawer-exploit-table-wrap">
            <table className="drawer-exploit-table mono" aria-label="Public exploits">
              <thead>
                <tr>
                  <th scope="col">Type</th>
                  <th scope="col">Source</th>
                  <th scope="col">Title</th>
                  <th scope="col">Link</th>
                </tr>
              </thead>
              <tbody>
                {exploits.map((exp, idx) => (
                  <tr key={exp.url || `${exp.title}-${idx}`}>
                    <td>
                      <span
                        className={`drawer-exploit-type mono drawer-exploit-type--${(exp.type || 'poc').toLowerCase()}`}
                      >
                        {exploitTypeLabel(exp.type)}
                      </span>
                    </td>
                    <td className="drawer-exploit-source-cell">{exp.source || '—'}</td>
                    <td className="drawer-exploit-title-cell">{exploitDisplayTitle(exp)}</td>
                    <td>
                      {exp.url ? (
                        <a
                          className="drawer-exploit-link mono"
                          href={exp.url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Open ↗
                        </a>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {exploits.some(exp => exp.requires_terms_acceptance) && (
          <p className="drawer-intel-hint mono">
            // Packet Storm links open in your browser and require a one-time Terms acceptance (once per session).
          </p>
        )}
      </section>

      <section className="drawer-section" aria-labelledby="scanning-heading">
        <h3 id="scanning-heading" className="drawer-human-label mono">// ACTIVE SCANNING</h3>
        {greynoiseConfigured === false ? (
          <p className="drawer-intel-empty mono">
            GreyNoise is not configured on this server — on-demand IP context is unavailable.
          </p>
        ) : greynoiseLoading ? (
          <p className="drawer-intel-empty mono">// Loading GreyNoise scanning context…</p>
        ) : !greynoiseLoaded && scans.length === 0 ? (
          <>
            <GreynoiseQuotaLine quota={greynoiseQuota} />
            <p className="drawer-intel-empty mono">
              // IPs are not looked up automatically — uses your weekly GreyNoise quota (50/week)
            </p>
            {onLoadGreynoise && (
              <button
                type="button"
                className="drawer-gn-load-btn mono"
                onClick={onLoadGreynoise}
              >
                Load GreyNoise scanning
              </button>
            )}
          </>
        ) : scans.length === 0 ? (
          <>
            <GreynoiseQuotaLine quota={greynoiseQuota} />
            <p className="drawer-intel-empty mono">
              // No exploitation-related IPs found in this CVE record
            </p>
            {onLoadGreynoise && (
              <button type="button" className="drawer-gn-load-btn mono" onClick={onLoadGreynoise}>
                Retry GreyNoise
              </button>
            )}
          </>
        ) : (
          <>
            <GreynoiseQuotaLine quota={greynoiseQuota} />
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
                      → Add to investigation
                    </button>
                  )}
                </li>
              )
            })}
          </ul>
          </>
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
          <CampaignPulseGroups
            pulses={pulses}
            cve={cve}
            onInvestigatePulse={onInvestigatePulse}
          />
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
        onRequestSuppress={onRequestSuppressCorrelation}
        suppressions={suppressions}
        onRestoreSuppression={onRestoreSuppression}
        cve={cve}
        onInvestigateCampaign={onInvestigateCampaign}
      />
    </>
  )
}
