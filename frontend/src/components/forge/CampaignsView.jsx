import { useCallback, useEffect, useState } from 'react'
import { fetchCorrelationClusters } from '../../api.js'
import { notifyApiError } from '../Toast.jsx'
import Tooltip from '../ui/Tooltip.jsx'
import { ingestLogUrl } from '../../utils/adminLinks.js'
import { useInvestigationOptional } from '../../context/InvestigationContext.jsx'
import { campaignBadgeTooltip, campaignLifecycleClass } from '../../utils/correlationPresentation.js'
import { clusterOpenTarget, openCvesLabel } from '../../utils/campaignClusterOpen.js'
import { SkeletonRows } from './shared.jsx'

export default function CampaignsView({ profileStack }) {
  const investigation = useInvestigationOptional()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)

  const reloadClusters = useCallback((isActive = () => true) => {
    setLoading(true)
    setError(null)
    setErrorRequestId(null)
    return fetchCorrelationClusters({ stack: profileStack || '', limit: 25 })
      .then(payload => { if (isActive()) setData(payload) })
      .catch(err => {
        if (!isActive()) return
        setError(err.message || 'Failed to load campaign clusters')
        setErrorRequestId(err?.requestId || null)
        notifyApiError(err)
      })
      .finally(() => { if (isActive()) setLoading(false) })
  }, [profileStack])

  useEffect(() => {
    let active = true
    reloadClusters(() => active)
    return () => { active = false }
  }, [reloadClusters])

  const openClusterCve = (cluster) => {
    const target = clusterOpenTarget(cluster)
    if (!target || !investigation?.openCveById) return
    investigation.openCveById(target)
  }

  return (
    <section className="fg-backlog-section" aria-label="Campaign clusters">
      <h2 className="fg-section-label mono">CAMPAIGN CLUSTERS</h2>
      <p className="fg-panel-hint mono">
        OTX pulse groupings ranked for your stack and pinned CVEs. Open a member CVE to inspect correlation in the drawer.
      </p>
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
          {profileStack
            ? '// No active campaign clusters match your stack yet — wait for OTX sync and correlation rebuild'
            : '// No active campaign clusters yet — load My Stack or wait for OTX correlation'}
        </p>
      ) : (
        <ul className="fg-backlog-list fg-campaign-list">
          {data.clusters.map(cluster => {
            const lifecycle = cluster.lifecycle || 'active'
            const target = clusterOpenTarget(cluster)
            const canOpen = Boolean(target && investigation?.openCveById)
            const label = openCvesLabel(cluster.member_count)
            return (
              <li key={cluster.campaign_id} className="fg-backlog-row fg-campaign-row">
                <div className="fg-backlog-main">
                  <span className="fg-cve-id mono">{cluster.label || cluster.campaign_id}</span>
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
                <div className="fg-backlog-actions">
                  <Tooltip
                    text={
                      canOpen
                        ? `Open ${target} in the drawer (first stack, pinned, or campaign member).`
                        : 'No openable member CVE for this cluster.'
                    }
                  >
                    <button
                      type="button"
                      className="fg-generate-btn mono"
                      onClick={() => openClusterCve(cluster)}
                      disabled={!canOpen}
                      aria-label={
                        canOpen
                          ? `${label}: open ${target} from ${cluster.label || cluster.campaign_id}`
                          : `${label} unavailable — no member CVE`
                      }
                    >
                      {label}
                    </button>
                  </Tooltip>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
