import { useEffect, useState } from 'react'
import { fetchSecurityArchitectureNodeContext } from '../../api.js'
import { notifyApiError } from '../../components/Toast.jsx'
import AsyncState from '../../components/ui/AsyncState.jsx'

const KIND_LABEL = {
  component: 'ROUTER',
  job: 'SCHEDULER JOB',
  table: 'DB TABLE',
  core: 'CORE MODULE',
  external: 'EXTERNAL SOURCE',
}

/**
 * Context rail content for a selected architecture-graph node (spec §5.2
 * node selection panel, §8 TM-4: "node selection populates the context
 * rail"). Lives in the persistent right rail (SecurityArchitecturePage.jsx)
 * so selecting a node never reflows the graph/workspace panel -- the rail
 * is a fixed-width sticky column (playbook §3 smoothness budget: "zero
 * layout shift when selecting a node").
 */
export default function ContextRail({ nodeId, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSecurityArchitectureNodeContext(nodeId)
      .then(res => { if (!cancelled) setData(res) })
      .catch(err => {
        if (!cancelled) {
          setError(err)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [nodeId, reloadKey])

  return (
    <div className="sa-rail-content">
      <div className="sa-rail-selection-head">
        <span className="sa-rail-kind mono">{KIND_LABEL[data?.kind] || 'NODE'}</span>
        <button type="button" className="sa-rail-close" aria-label="Close context" onClick={onClose}>✕</button>
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error)}
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        {data && (
          <>
            <h3 className="sa-rail-title">{data.label}</h3>
            {data.summary && <p className="sa-row-summary">{data.summary}</p>}
            {data.owner && <p className="sa-rail-meta mono">owner: {data.owner}</p>}

            {data.endpoints?.length > 0 && (
              <section className="sa-rail-section">
                <h4 className="sa-subsection-label mono">API ENDPOINTS ({data.endpoints.length})</h4>
                <ul className="sa-row-list">
                  {data.endpoints.map(e => (
                    <li key={`${e.method}-${e.path}`} className="sa-rail-line mono">
                      <span className="sa-row-tag mono">{e.method}</span> {e.path}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {data.controls?.length > 0 && (
              <section className="sa-rail-section">
                <h4 className="sa-subsection-label mono">SECURITY CONTROLS ({data.controls.length})</h4>
                <ul className="sa-row-list">
                  {data.controls.map(c => (
                    <li key={c.id} className="sa-rail-line">{c.title}</li>
                  ))}
                </ul>
              </section>
            )}

            {data.tables?.length > 0 && (
              <section className="sa-rail-section">
                <h4 className="sa-subsection-label mono">DATABASE TABLES ({data.tables.length})</h4>
                <ul className="sa-row-list">
                  {data.tables.map(t => (
                    <li key={t.id} className="sa-rail-line mono">{t.label}</li>
                  ))}
                </ul>
              </section>
            )}

            {data.externals?.length > 0 && (
              <section className="sa-rail-section">
                <h4 className="sa-subsection-label mono">EXTERNAL SOURCES ({data.externals.length})</h4>
                <ul className="sa-row-list">
                  {data.externals.map(n => (
                    <li key={n.id} className="sa-rail-line mono">{n.label}</li>
                  ))}
                </ul>
              </section>
            )}

            {data.referenced_by?.length > 0 && (
              <section className="sa-rail-section">
                <h4 className="sa-subsection-label mono">REFERENCED BY ({data.referenced_by.length})</h4>
                <ul className="sa-row-list">
                  {data.referenced_by.map(n => (
                    <li key={n.id} className="sa-rail-line mono">{n.label}</li>
                  ))}
                </ul>
              </section>
            )}

            {data.fetched_by?.length > 0 && (
              <section className="sa-rail-section">
                <h4 className="sa-subsection-label mono">FETCHED BY ({data.fetched_by.length})</h4>
                <ul className="sa-row-list">
                  {data.fetched_by.map(n => (
                    <li key={n.id} className="sa-rail-line mono">{n.label}</li>
                  ))}
                </ul>
              </section>
            )}

            {data.source_refs?.length > 0 && (
              <section className="sa-rail-section">
                <h4 className="sa-subsection-label mono">SOURCE</h4>
                <ul className="sa-row-list">
                  {data.source_refs.map(r => (
                    <li key={r.ref} className="sa-rail-line mono">{r.ref}</li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}
      </AsyncState>
    </div>
  )
}
