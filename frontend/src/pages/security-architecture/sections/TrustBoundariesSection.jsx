import { useEffect, useState } from 'react'
import { fetchSecurityArchitectureSection } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'

const RESIDUAL_HELP = {
  low: 'Controls in place cover the identified threats for this boundary.',
  medium: 'Some threats are mitigated; residual exposure remains and is tracked here, not hidden.',
  high: 'Significant residual exposure — treat as a priority for the next security review.',
  critical: 'Unmitigated exposure at a trust boundary — highest priority.',
}

/**
 * Trust Boundaries (spec §5.3, §8 TM-4): vertical flow cards for each
 * curated boundary crossing. Reads the same GET /section/trust_boundaries
 * endpoint GenericSection used pre-TM-4 (data shape is a plain curated
 * record list -- no dedicated backend endpoint needed, spec §4.4's
 * /trust-boundaries route folds into the existing generic section read),
 * rendered here as the spec's "visual vertical flows" instead of a table.
 */
export default function TrustBoundariesSection() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureSection('trust_boundaries', {})
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

  const boundaries = data?.items || []
  const flowSteps = (title) => title.split('->').map(s => s.trim())

  return (
    <div className="sa-section">
      <h2 className="sa-section-title mono">TRUST BOUNDARIES</h2>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && boundaries.length === 0)}
        emptyTitle={error ? undefined : 'No trust boundaries curated yet.'}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <div className="sa-tb-list">
          {boundaries.map(b => (
            <div key={b.id} className="sa-tb-card">
              <div className="sa-tb-flow" aria-label={b.title}>
                {flowSteps(b.title).map((step, i, arr) => (
                  <span key={step} className="sa-tb-flow-step">
                    <span className="sa-tb-flow-node mono">{step}</span>
                    {i < arr.length - 1 && <span className="sa-tb-flow-arrow" aria-hidden="true">↓</span>}
                  </span>
                ))}
              </div>
              <p className="sa-row-summary">{b.summary}</p>
              <dl className="sa-tb-fields">
                <div className="sa-tb-field">
                  <dt className="sa-subsection-label mono">DATA CLASSIFICATION</dt>
                  <dd>{b.data_classification || '—'}</dd>
                </div>
                <div className="sa-tb-field">
                  <dt className="sa-subsection-label mono">AUTHENTICATION</dt>
                  <dd>{b.authentication || '—'}</dd>
                </div>
                <div className="sa-tb-field">
                  <dt className="sa-subsection-label mono">ENCRYPTION</dt>
                  <dd>{b.encryption || '—'}</dd>
                </div>
                <div className="sa-tb-field">
                  <dt className="sa-subsection-label mono">CONTROLS</dt>
                  <dd>
                    {(b.controls || []).map(c => (
                      <span key={c} className="sa-row-tag mono">{c}</span>
                    ))}
                    {(!b.controls || b.controls.length === 0) && '—'}
                  </dd>
                </div>
              </dl>
              {b.residual_risk && (
                <Tooltip text={RESIDUAL_HELP[b.residual_risk] || b.residual_risk}>
                  <span className={`sa-status-chip sa-status-${b.residual_risk} mono sa-tb-residual`}>
                    RESIDUAL RISK: {b.residual_risk.toUpperCase()}
                  </span>
                </Tooltip>
              )}
            </div>
          ))}
        </div>
      </AsyncState>
    </div>
  )
}
