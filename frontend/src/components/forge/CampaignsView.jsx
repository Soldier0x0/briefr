import { useCallback, useEffect, useState } from 'react'
import { fetchCorrelationClusters, fetchWatchlist } from '../../api.js'
import { notifyApiError } from '../Toast.jsx'
import Tooltip from '../ui/Tooltip.jsx'
import { ingestLogUrl } from '../../utils/adminLinks.js'
import { useInvestigationOptional } from '../../context/InvestigationContext.jsx'
import { campaignBadgeTooltip, campaignLifecycleClass } from '../../utils/correlationPresentation.js'
import { clusterMemberInventory, openCvesLabel } from '../../utils/campaignClusterOpen.js'
import { formatIntelLabelText } from '../../utils/formatIntelLabel.js'
import {
  browseGlobalUnpersonalizedLabel,
  campaignsEmptyGuidance,
  campaignsPanelHint,
  hasPersonalizationContext,
  unpersonalizedBadgeLabel,
} from '../../utils/personalizationCopy.js'
import { SkeletonRows } from './shared.jsx'

export default function CampaignsView({ profileStack }) {
  const investigation = useInvestigationOptional()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)
  const [pinCount, setPinCount] = useState(0)
  const [browseGlobal, setBrowseGlobal] = useState(false)

  const hasStack = Boolean(String(profileStack || '').trim())
  const hasPins = pinCount > 0
  const personalized = hasPersonalizationContext({
    stackTerms: profileStack,
    pinCount,
  })
  const showClusters = personalized || browseGlobal

  useEffect(() => {
    let active = true
    fetchWatchlist()
      .then((payload) => {
        if (!active) return
        const entries = Array.isArray(payload?.data) ? payload.data : []
        setPinCount(entries.filter((row) => row?.state === 'pin').length)
      })
      .catch(() => {
        if (active) setPinCount(0)
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    // Stack/pins arrived — drop the unpersonalized browse latch.
    if (personalized) setBrowseGlobal(false)
  }, [personalized])

  const reloadClusters = useCallback((isActive = () => true) => {
    setLoading(true)
    setError(null)
    setErrorRequestId(null)
    const stackParam = personalized ? (profileStack || '') : ''
    return fetchCorrelationClusters({ stack: stackParam, limit: 25 })
      .then(payload => { if (isActive()) setData(payload) })
      .catch(err => {
        if (!isActive()) return
        setError(err.message || 'Failed to load campaign clusters')
        setErrorRequestId(err?.requestId || null)
        notifyApiError(err)
      })
      .finally(() => { if (isActive()) setLoading(false) })
  }, [profileStack, personalized])

  useEffect(() => {
    if (!showClusters) {
      setData(null)
      setLoading(false)
      setError(null)
      setErrorRequestId(null)
      return undefined
    }
    let active = true
    reloadClusters(() => active)
    return () => { active = false }
  }, [reloadClusters, showClusters])

  const openMemberCve = (cveId) => {
    if (!cveId || !investigation?.openCveById) return
    investigation.openCveById(cveId)
  }

  return (
    <section className="fg-backlog-section" aria-label="Campaign clusters">
      <h2 className="fg-section-label mono">CAMPAIGN CLUSTERS</h2>
      {!showClusters ? (
        <div className="fg-campaign-guidance">
          <p className="fg-panel-empty mono">{campaignsEmptyGuidance()}</p>
          <button
            type="button"
            className="fg-secondary-btn mono"
            onClick={() => setBrowseGlobal(true)}
          >
            {browseGlobalUnpersonalizedLabel()}
          </button>
        </div>
      ) : (
        <>
          {loading && !data ? (
            <SkeletonRows count={4} />
          ) : error ? (
            <div className="fg-error-block">
              <p className="fg-error mono">
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
              <button type="button" className="fg-error-retry-btn mono" onClick={() => reloadClusters()}>
                Retry
              </button>
            </div>
          ) : (data?.clusters || []).length === 0 ? (
            <p className="fg-panel-empty mono">
              {personalized
                ? '// No active campaign clusters match your stack yet — wait for OTX sync and correlation rebuild'
                : '// No active campaign clusters yet — wait for OTX sync and correlation rebuild'}
              {!personalized && browseGlobal && (
                <>
                  {' '}
                  <span className="fg-unpersonalized-badge mono">{unpersonalizedBadgeLabel()}</span>
                </>
              )}
            </p>
          ) : (
            <>
              <p className="fg-panel-hint mono">
                {campaignsPanelHint({ hasStack, hasPins })}
                {!personalized && browseGlobal && (
                  <>
                    {' '}
                    <span className="fg-unpersonalized-badge mono">{unpersonalizedBadgeLabel()}</span>
                  </>
                )}
              </p>
              <ul className="fg-backlog-list fg-campaign-list">
                {data.clusters.map(cluster => {
                  const lifecycle = cluster.lifecycle || 'active'
                  const members = clusterMemberInventory(cluster)
                  const canOpen = Boolean(investigation?.openCveById)
                  const rawClusterLabel = cluster.label || cluster.campaign_id
                  const clusterLabel = formatIntelLabelText(rawClusterLabel) || rawClusterLabel
                  const inventoryAria = members.length === 1
                    ? openCvesLabel(1)
                    : `${members.length} member CVEs`
                  return (
                    <li key={cluster.campaign_id} className="fg-backlog-row fg-campaign-row">
                      <div className="fg-backlog-main">
                        <span className="fg-cve-id mono" title={typeof rawClusterLabel === 'string' ? rawClusterLabel : undefined}>
                          {clusterLabel}
                        </span>
                        <Tooltip text={campaignBadgeTooltip(lifecycle)}>
                          <span className={`fg-lifecycle-badge mono ${campaignLifecycleClass(lifecycle)}`}>
                            {(lifecycle || 'active').toUpperCase()}
                          </span>
                        </Tooltip>
                        {cluster.adversary && (
                          <span className="fg-backlog-tech-name">{cluster.adversary}</span>
                        )}
                        <span className="fg-backlog-tech mono">
                          {cluster.member_count} CVE{cluster.member_count === 1 ? '' : 's'}
                        </span>
                        {cluster.watchlisted_member_count > 0 && (
                          <span className="fg-backlog-due mono">
                            {cluster.watchlisted_member_count} pinned
                          </span>
                        )}
                        {profileStack && cluster.stack_member_count > 0 && (
                          <span className="fg-backlog-due mono">
                            {cluster.stack_member_count} on stack
                          </span>
                        )}
                      </div>
                      <div className="fg-campaign-members" aria-label={inventoryAria}>
                        {members.length === 0 ? (
                          <span className="fg-panel-empty mono">// No member CVEs</span>
                        ) : (
                          members.map((cveId) => (
                            canOpen ? (
                              <button
                                key={cveId}
                                type="button"
                                className="fg-cve-id mono fg-cve-id-link"
                                onClick={() => openMemberCve(cveId)}
                                title={`Open ${cveId} in drawer`}
                                aria-label={
                                  members.length === 1
                                    ? `${openCvesLabel(1)}: ${cveId}`
                                    : `Open ${cveId}`
                                }
                              >
                                {cveId}
                              </button>
                            ) : (
                              <span key={cveId} className="fg-cve-id mono">{cveId}</span>
                            )
                          ))
                        )}
                      </div>
                    </li>
                  )
                })}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  )
}
