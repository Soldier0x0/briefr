import { useEffect, useMemo, useState } from 'react'
import { fetchSecurityArchitectureSection } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'

const STALE_HELP = 'This abuse case has not been reviewed in over 90 days (spec §4.1 staleness decay).'
const STATUS_HELP = {
  mitigated: 'Real protection code exists and is cited as evidence.',
  partial: 'Some protection exists but a gap remains -- see "Remaining risk".',
  open: 'No mitigating control exists yet -- an honest, unmitigated finding.',
}

/**
 * Abuse Case Catalog (spec §5.11, §8 TM-5): searchable list. Every entry's
 * `current_protection` cites real code (security_architecture/corpus/
 * abuse_cases.yaml) -- a curated abuse case with no verifiable protection
 * behind it would be exactly the "documentation viewer" the module's
 * central principle forbids.
 */
export default function AbuseCasesSection() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [query, setQuery] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureSection('abuse_cases', {})
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

  const allRows = data?.items || []
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return allRows
    return allRows.filter(r =>
      (r.title || '').toLowerCase().includes(q) ||
      (r.summary || '').toLowerCase().includes(q) ||
      (r.category || '').toLowerCase().includes(q),
    )
  }, [allRows, query])

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">ABUSE CASES</h2>
        {data && <p className="sa-mitre-counts mono">{allRows.length} case{allRows.length === 1 ? '' : 's'}</p>}
      </div>

      <form className="sa-stack-filter" onSubmit={(e) => e.preventDefault()}>
        <label className="sa-subsection-label mono" htmlFor="sa-abuse-search">SEARCH</label>
        <input
          id="sa-abuse-search"
          type="text"
          className="sa-stack-input mono"
          placeholder="e.g. ssrf, replay, rate limit"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </form>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && rows.length === 0)}
        emptyTitle={
          error
            ? undefined
            : query
              ? `No abuse cases match "${query}".`
              : 'No abuse cases yet — curated, empty until a security-review pass populates abuse_cases.yaml.'
        }
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <ul className="sa-row-list" aria-label="Abuse case catalog">
          {rows.map(a => (
            <li key={a.id} className="sa-row">
              <div className="sa-row-main">
                <span className="sa-row-title">{a.title}</span>
                {a.category && <span className="sa-row-tag mono">{a.category}</span>}
                {a.status && (
                  <Tooltip text={STATUS_HELP[a.status] || a.status}>
                    <span className={`sa-status-chip sa-status-${a.status === 'open' ? 'critical' : a.status === 'partial' ? 'medium' : 'low'} mono`}>
                      {a.status.toUpperCase()}
                    </span>
                  </Tooltip>
                )}
                {a.stale && (
                  <Tooltip text={STALE_HELP}>
                    <span className="sa-status-chip sa-status-critical mono">STALE</span>
                  </Tooltip>
                )}
              </div>
              {a.summary && <p className="sa-row-summary">{a.summary}</p>}

              {Array.isArray(a.attack_flow) && a.attack_flow.length > 0 && (
                <div className="sa-decision-field">
                  <h4 className="sa-subsection-label mono">ATTACK FLOW</h4>
                  <ol>
                    {a.attack_flow.map((step, i) => <li key={i}>{step}</li>)}
                  </ol>
                </div>
              )}
              {a.impact && (
                <div className="sa-decision-field">
                  <h4 className="sa-subsection-label mono">IMPACT</h4>
                  <p>{a.impact}</p>
                </div>
              )}
              {a.current_protection && (
                <div className="sa-decision-field">
                  <h4 className="sa-subsection-label mono">CURRENT PROTECTION</h4>
                  <p>{a.current_protection}</p>
                </div>
              )}
              {a.remaining_risk && (
                <div className="sa-decision-field">
                  <h4 className="sa-subsection-label mono">REMAINING RISK</h4>
                  <p>{a.remaining_risk}</p>
                </div>
              )}
            </li>
          ))}
        </ul>
      </AsyncState>
    </div>
  )
}
