import { useEffect, useState } from 'react'
import { fetchSecurityArchitectureSection } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'

const STALE_HELP = 'This decision record has not been reviewed in over 90 days (spec §4.1 staleness decay).'

/**
 * Security Decision Records (spec §5.13, §8 TM-5): ADR-style list. Every
 * record here maps a real ADR in docs/decisions/ -- decision, alternatives,
 * tradeoffs, and consequences fields are drawn directly from the ADR text
 * (security_architecture/corpus/security_decisions.yaml), not invented.
 */
export default function DecisionsSection() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [expanded, setExpanded] = useState(() => new Set())

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureSection('security_decisions', {})
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

  function toggle(id) {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">SECURITY DECISIONS</h2>
        {data && <p className="sa-mitre-counts mono">{data.count} record{data.count === 1 ? '' : 's'}</p>}
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && rows.length === 0)}
        emptyTitle={error ? undefined : 'No decision records yet — curated, empty until an ADR is mapped into the corpus.'}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <ul className="sa-row-list" aria-label="Security decision records">
          {rows.map(d => {
            const isOpen = expanded.has(d.id)
            return (
              <li key={d.id} className="sa-row sa-decision-row">
                <button
                  type="button"
                  className="sa-decision-toggle"
                  aria-expanded={isOpen}
                  onClick={() => toggle(d.id)}
                >
                  <div className="sa-row-main">
                    <span className="sa-row-title">{d.title}</span>
                    {d.status && <span className="sa-row-tag mono">{d.status}</span>}
                    {d.stale && (
                      <Tooltip text={STALE_HELP}>
                        <span className="sa-status-chip sa-status-critical mono">STALE</span>
                      </Tooltip>
                    )}
                    <span className="sa-decision-caret mono">{isOpen ? '▾' : '▸'}</span>
                  </div>
                  {d.summary && <p className="sa-row-summary">{d.summary}</p>}
                </button>

                {isOpen && (
                  <div className="sa-decision-detail">
                    {d.decision && (
                      <div className="sa-decision-field">
                        <h4 className="sa-subsection-label mono">DECISION</h4>
                        <p>{d.decision}</p>
                      </div>
                    )}
                    {Array.isArray(d.alternatives) && d.alternatives.length > 0 && (
                      <div className="sa-decision-field">
                        <h4 className="sa-subsection-label mono">ALTERNATIVES CONSIDERED</h4>
                        <ul>
                          {d.alternatives.map((a, i) => <li key={i}>{a}</li>)}
                        </ul>
                      </div>
                    )}
                    {d.tradeoffs && (
                      <div className="sa-decision-field">
                        <h4 className="sa-subsection-label mono">TRADEOFFS</h4>
                        <p>{d.tradeoffs}</p>
                      </div>
                    )}
                    {d.consequences && (
                      <div className="sa-decision-field">
                        <h4 className="sa-subsection-label mono">CONSEQUENCES</h4>
                        <p>{d.consequences}</p>
                      </div>
                    )}
                    {d.adr_ref && (
                      <p className="sa-decision-source mono">source: {d.adr_ref}</p>
                    )}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      </AsyncState>
    </div>
  )
}
