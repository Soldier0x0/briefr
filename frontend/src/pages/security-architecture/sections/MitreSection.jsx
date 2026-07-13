import { useEffect, useState } from 'react'
import { fetchSecurityArchitectureMitre } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'

const STATUS_LABEL = { yours: 'YOURS', community: 'COMMUNITY', gap: 'GAP' }
const STATUS_HELP = {
  yours: 'At least one saved hunt pack exists for this technique.',
  community: 'The bundled community Sigma/SIEM template library covers this technique.',
  gap: 'No saved or bundled detection content covers this technique — a real detection-engineering gap.',
}

/**
 * MITRE ATT&CK section (TM-3, spec §5.6). Live coverage matrix -- reuses
 * routers.forge.build_coverage_map (security_architecture/merge.py
 * docstring), so "coverage matches DB" holds by construction rather than by
 * a second implementation staying in sync with the first.
 *
 * Grouped-by-tactic dense list rather than the spec's aspirational SVG heat
 * matrix -- TM-3 acceptance (technique click opens Forge link; coverage
 * matches DB; stack filter works) doesn't require the matrix visualization,
 * and the only *live* coverage layer this codebase actually has is
 * Detection (hunt packs / bundled templates) -- Correlation/YARA/AI layers
 * from spec §5.6's table have no live data source yet, so they're not
 * fabricated here (central principle: no invented arithmetic/rows).
 */
export default function MitreSection() {
  const [stackInput, setStackInput] = useState('')
  const [stack, setStack] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureMitre(stack)
      .then(res => { if (!cancelled) setData(res) })
      .catch(err => {
        if (!cancelled) {
          setError(err)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [stack, reloadKey])

  const techniques = data?.techniques || []
  const byTactic = techniques.reduce((acc, t) => {
    const key = t.tactic || 'unclassified'
    ;(acc[key] ||= []).push(t)
    return acc
  }, {})

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">MITRE ATT&amp;CK</h2>
        {data?.meta?.counts && (
          <p className="sa-mitre-counts mono">
            {data.meta.counts.gap} gap · {data.meta.counts.community} community · {data.meta.counts.yours} yours
          </p>
        )}
      </div>

      <form
        className="sa-stack-filter"
        onSubmit={(e) => { e.preventDefault(); setStack(stackInput.trim()) }}
      >
        <label className="sa-subsection-label mono" htmlFor="sa-mitre-stack">STACK FILTER</label>
        <input
          id="sa-mitre-stack"
          type="text"
          className="sa-stack-input mono"
          placeholder="e.g. apache, log4j (comma-separated, same matching as Forge)"
          value={stackInput}
          onChange={(e) => setStackInput(e.target.value)}
        />
        <button type="submit" className="admin-btn admin-btn-ghost mono">APPLY</button>
        {stack && (
          <button
            type="button"
            className="admin-btn admin-btn-ghost mono"
            onClick={() => { setStackInput(''); setStack('') }}
          >
            CLEAR
          </button>
        )}
      </form>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || (!loading && techniques.length === 0)}
        emptyTitle={error ? undefined : 'No techniques linked to CVEs in the database yet.'}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        {Object.entries(byTactic).sort(([a], [b]) => a.localeCompare(b)).map(([tactic, items]) => (
          <div key={tactic} className="sa-mitre-tactic-group">
            <h3 className="sa-subsection-label mono">{tactic.toUpperCase()}</h3>
            <ul className="sa-row-list" aria-label={`${tactic} techniques`}>
              {items.map(t => (
                <li key={t.technique_id} className="sa-row">
                  <div className="sa-row-main">
                    <a
                      className="sa-row-title sa-mitre-link"
                      href={`/?view=coverage&technique=${encodeURIComponent(t.technique_id)}`}
                      title="Open in Forge"
                    >
                      {t.technique_id} — {t.name || t.technique_id}
                    </a>
                    <Tooltip text={STATUS_HELP[t.status] || t.status}>
                      <span className={`sa-status-chip sa-status-${t.status} mono`}>
                        {STATUS_LABEL[t.status] || t.status}
                      </span>
                    </Tooltip>
                    <span className="sa-row-tag mono">{t.cve_count} CVE</span>
                    {t.kev_count > 0 && <span className="sa-row-tag sa-row-tag-kev mono">{t.kev_count} KEV</span>}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </AsyncState>
    </div>
  )
}
