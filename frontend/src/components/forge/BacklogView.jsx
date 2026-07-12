import { useCallback, useEffect, useState } from 'react'
import { dismissDetectionBacklogItem, fetchDetectionBacklog } from '../../api.js'
import { notifyApiError } from '../Toast.jsx'
import Tooltip from '../ui/Tooltip.jsx'
import { ingestLogUrl } from '../../utils/adminLinks.js'
import { SkeletonRows, StatusChip } from './shared.jsx'

export default function BacklogView({ profileStack, onGeneratePack, generatingCve, onDismissed }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)
  const [dismissingId, setDismissingId] = useState(null)

  const loadBacklog = useCallback(() => {
    setLoading(true)
    setError(null)
    setErrorRequestId(null)
    return fetchDetectionBacklog({ stack: profileStack || '' })
      .then(setData)
      .catch(err => {
        setError(err.message || 'Failed to load detection backlog')
        setErrorRequestId(err?.requestId || null)
        notifyApiError(err)
      })
      .finally(() => setLoading(false))
  }, [profileStack])

  useEffect(() => {
    loadBacklog()
  }, [loadBacklog])

  const handleDismiss = useCallback((itemId) => {
    setDismissingId(itemId)
    dismissDetectionBacklogItem(itemId)
      .then(() => {
        onDismissed?.()
        return loadBacklog()
      })
      .catch(err => notifyApiError(err))
      .finally(() => setDismissingId(null))
  }, [loadBacklog, onDismissed])

  const items = data?.items || []

  return (
    <section className="fg-backlog-section" aria-label="Detection backlog">
      <h2 className="fg-section-label mono">KEV DETECTION BACKLOG</h2>
      {!profileStack ? (
        <p className="fg-panel-empty mono">
          // Load an asset profile (My Stack) to see KEV-driven detection gaps on your stack
        </p>
      ) : loading && !data ? (
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
          <button type="button" className="fg-error-retry-btn mono" onClick={loadBacklog}>
            Retry
          </button>
        </div>
      ) : items.length === 0 ? (
        <p className="fg-panel-empty mono">
          // No open KEV detection gaps on your stack — backlog fills when new KEV entries match uncovered techniques
        </p>
      ) : (
        <ul className="fg-backlog-list">
          {items.map(item => (
            <li key={item.id} className="fg-backlog-row">
              <div className="fg-backlog-main">
                <span className="fg-cve-id mono">{item.cve_id}</span>
                <span className="fg-backlog-tech mono">{item.technique_id}</span>
                <span className="fg-backlog-tech-name">{item.technique_name}</span>
                <Tooltip text="Derived from KEV status plus CVSS/EPSS when not KEV.">
                  <span className={`fg-priority fg-priority-${item.priority} mono`}>
                    {item.priority.toUpperCase()}
                  </span>
                </Tooltip>
                <Tooltip text="No saved hunt pack and no bundled community template for this technique.">
                  <StatusChip status="gap" />
                </Tooltip>
                {item.kev_due_date && (
                  <span className="fg-backlog-due mono">KEV due {item.kev_due_date}</span>
                )}
              </div>
              <div className="fg-backlog-actions">
                <button
                  type="button"
                  className="fg-generate-btn mono"
                  onClick={() => onGeneratePack(item.cve_id, item.technique_id)}
                  disabled={generatingCve === item.cve_id}
                >
                  {generatingCve === item.cve_id ? 'GENERATING…' : 'GENERATE PACK'}
                </button>
                <button
                  type="button"
                  className="fg-backlog-dismiss mono"
                  onClick={() => handleDismiss(item.id)}
                  disabled={dismissingId === item.id}
                >
                  {dismissingId === item.id ? 'DISMISSING…' : 'DISMISS'}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
