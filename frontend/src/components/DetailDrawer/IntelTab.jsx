import { useMemo, useState } from 'react'
import { displayText } from '../../utils/displayText.js'
import DrawerAtlasSection from '../DrawerAtlasSection.jsx'
import { exploitTypeLabel, techniqueLink } from './helpers.js'


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
        {(pulse.targeted_countries || []).filter(Boolean).slice(0, 6).map((cc, ccIdx) => (
          <span
            key={`${cc}-${ccIdx}`}
            className="drawer-otx-country mono"
            title="Country targeted in this OTX pulse (AlienVault OTX community intelligence)"
          >
            {String(cc).toUpperCase()}
          </span>
        ))}
      </div>
      {onInvestigatePulse && pulse.pulse_id && (
        <button type="button" className="drawer-investigate-btn" onClick={() => onInvestigatePulse(pulse, cve)}>
          → Investigate IOCs
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
export default function TabIntel({ techniques, publicExploits, greynoiseScans, otxPulses, otxConfigured, cve, loading, onInvestigateIp, onInvestigatePulse, pivotNotice, correlation, correlationLoading, onSelectCorrelatedCve, onDismissCorrelation }) {
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
        onDismiss={onDismissCorrelation}
      />
    </>
  )
}
