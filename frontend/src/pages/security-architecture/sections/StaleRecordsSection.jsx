import { useEffect, useState } from 'react'
import { fetchSecurityArchitectureStale } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'

const SECTION_LABEL = {
  components: 'Components', trust_boundaries: 'Trust Boundaries', controls: 'Controls',
  abuse_cases: 'Abuse Cases', threat_scenarios: 'Threat Scenarios',
  security_decisions: 'Security Decisions', risks: 'Risk Register', reviews: 'Review History',
}

/**
 * Stale Records (spec §5.1 "Stale Records" tile drill-through, §9.6): every
 * curated record across every section past the 90-day review window. Not a
 * manifest nav section of its own -- reached only via the Overview tile,
 * same convention as `components` fanning across generated collections.
 */
export default function StaleRecordsSection({ onOpenSection }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureStale()
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

  const rows = data?.items || []

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">STALE RECORDS</h2>
        {data && <p className="sa-mitre-counts mono">{data.count} record{data.count === 1 ? '' : 's'} past the 90-day review window</p>}
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && rows.length === 0)}
        emptyTitle={error ? undefined : 'No stale records — every curated record has been reviewed within the last 90 days.'}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <ul className="sa-row-list" aria-label="Stale records">
          {rows.map((r, i) => (
            <li key={`${r.section}-${r.id || i}`} className="sa-row">
              <div className="sa-row-main">
                <span className="sa-row-title">{r.title}</span>
                <button
                  type="button"
                  className="sa-row-tag mono sa-mitre-link"
                  onClick={() => onOpenSection(r.section)}
                  title={`Open ${SECTION_LABEL[r.section] || r.section}`}
                >
                  {SECTION_LABEL[r.section] || r.section}
                </button>
                <span className="sa-status-chip sa-status-critical mono">STALE</span>
                {r.review_date && <span className="sa-row-tag mono">reviewed {r.review_date}</span>}
              </div>
              {r.summary && <p className="sa-row-summary">{r.summary}</p>}
            </li>
          ))}
        </ul>
      </AsyncState>
    </div>
  )
}
