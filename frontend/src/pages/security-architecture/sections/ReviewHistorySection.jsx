import { useEffect, useState } from 'react'
import { fetchSecurityArchitectureSection } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'

const STALE_HELP = 'This review record has not been refreshed in over 90 days (spec §4.1 staleness decay).'
const ORIGIN_HELP = {
  curated: 'A recorded security-review pass (architecture review, threat model review, ...).',
  live: 'A security-relevant audit_log event (auth, backup, config, restart, scheduler, integrity) -- same table and redaction rule as the Admin Audit Log.',
}

function eventTimestamp(item) {
  return item.review_date || item.occurred_at || ''
}

/**
 * Review History (spec §5.14, §8 TM-5): chronological timeline merging
 * curated reviews.yaml (real security-review passes this program
 * performed) with live audit_log security events (auth/backup/config/
 * restart/scheduler/integrity actions) -- reuses the existing audit_log
 * table and its masking rule, not a duplicate query.
 */
export default function ReviewHistorySection() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureSection('reviews', {})
      .then(res => { if (!cancelled) setData(res) })
      .catch(err => {
        if (!cancelled) {
          setError(err)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [reloadKey])

  const rows = [...(data?.items || [])].sort((a, b) => (eventTimestamp(b) > eventTimestamp(a) ? 1 : -1))

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">REVIEW HISTORY</h2>
        {data && <p className="sa-mitre-counts mono">{rows.length} event{rows.length === 1 ? '' : 's'}</p>}
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && rows.length === 0)}
        emptyTitle={error ? undefined : 'No review events yet — no curated review passes recorded and no matching security audit-log entries.'}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <ul className="sa-row-list sa-review-timeline" aria-label="Review history">
          {rows.map(r => (
            <li key={r.id} className="sa-row">
              <div className="sa-row-main">
                <span className="sa-row-title">{r.title || r.action}</span>
                <Tooltip text={ORIGIN_HELP[r.origin] || ''}>
                  <span className={`sa-row-origin sa-row-origin-${r.origin} mono`}>{r.origin}</span>
                </Tooltip>
                {r.review_type && <span className="sa-row-tag mono">{r.review_type}</span>}
                {r.status && <span className="sa-row-tag mono">{r.status}</span>}
                {r.stale && (
                  <Tooltip text={STALE_HELP}>
                    <span className="sa-status-chip sa-status-critical mono">STALE</span>
                  </Tooltip>
                )}
                <span className="sa-row-tag mono">{eventTimestamp(r)}</span>
              </div>
              {r.summary && <p className="sa-row-summary">{r.summary}</p>}
              {r.outcome && (
                <div className="sa-decision-field">
                  <h4 className="sa-subsection-label mono">OUTCOME</h4>
                  <p>{r.outcome}</p>
                </div>
              )}
              {Array.isArray(r.participants) && r.participants.length > 0 && (
                <p className="sa-rail-meta mono">participants: {r.participants.join(', ')}</p>
              )}
              {r.actor && r.origin === 'live' && (
                <p className="sa-rail-meta mono">actor: {r.actor}{r.target ? ` — target: ${r.target}` : ''}</p>
              )}
            </li>
          ))}
        </ul>
      </AsyncState>
    </div>
  )
}
