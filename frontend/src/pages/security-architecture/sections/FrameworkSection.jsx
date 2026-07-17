import { useEffect, useMemo, useState } from 'react'
import { fetchSecurityArchitectureFramework } from '../../../api.js'
import { notifyApiError } from '../../../components/Toast.jsx'
import AsyncState from '../../../components/ui/AsyncState.jsx'
import Tooltip from '../../../components/ui/Tooltip.jsx'
import ArchDataGrid from '../shared/ArchDataGrid.jsx'

/**
 * TM-6: shared analyst framework workspace (CWE / OWASP / CAPEC / STRIDE).
 *
 * Every framework is one lens on the same live aggregation -- the CWE weakness
 * classes present in `cves.cwe_ids` across the selected Scope (All CVEs / My
 * Stack / Watchlist / KEV). The Scope selector is the whole point of the
 * reframe: the frameworks describe the *user's own* threat surface, not
 * BRIEFR's. Each row's count drills through to the exact `example_cves` behind
 * it (opened in the CVE drawer), and the meta line always shows sample vs total
 * so a capped aggregation is visibly capped.
 */

const SCOPES = [
  { id: 'all', label: 'All CVEs', help: 'Every CVE ingested into BRIEFR.' },
  { id: 'stack', label: 'My Stack', help: 'CVEs matching your saved asset stack (or the terms you enter below) — same matching Forge uses.' },
  { id: 'watchlist', label: 'Watchlist', help: 'CVEs you are tracking on your watchlist.' },
  { id: 'kev', label: 'KEV only', help: 'CISA Known Exploited Vulnerabilities only.' },
]

const SEVERITIES = ['', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

const FRAMEWORK_META = {
  cwe: {
    title: 'CWE',
    subtitle: 'Weakness classes present across the selected CVEs, ranked by frequency (live cwe_ids).',
  },
  owasp: {
    title: 'OWASP Top 10',
    subtitle: 'Selected CVEs rolled up to OWASP Top 10 categories via each weakness’s official CWE list.',
  },
  capec: {
    title: 'CAPEC',
    subtitle: 'Attack patterns implied by the selected CVEs’ CWE weaknesses (MITRE CWE→CAPEC).',
  },
  stride: {
    title: 'STRIDE',
    subtitle: 'Threat classes of the selected CVEs’ CWE weaknesses (documented heuristic mapping).',
  },
}

function openCve(cveId) {
  if (!cveId) return
  window.open(`/?cve=${encodeURIComponent(cveId)}`, '_blank', 'noopener,noreferrer')
}

function ExampleCves({ items }) {
  if (!items?.length) return <span className="sa-fw-dim">—</span>
  return (
    <div className="sa-fw-examples">
      {items.map(e => (
        <button
          key={e.cve_id}
          type="button"
          className={`sa-cve-chip mono${e.is_kev ? ' sa-cve-chip-kev' : ''}`}
          onClick={() => openCve(e.cve_id)}
          title={`${e.severity || 'unrated'}${e.is_kev ? ' · CISA KEV' : ''} — open CVE`}
        >
          {e.cve_id}
        </button>
      ))}
    </div>
  )
}

function CweTags({ ids, limit = 6 }) {
  if (!ids?.length) return <span className="sa-fw-dim">—</span>
  const shown = ids.slice(0, limit)
  const extra = ids.length - shown.length
  return (
    <div className="sa-cwe-tags">
      {shown.map(id => <span key={id} className="sa-cwe-tag mono">{id}</span>)}
      {extra > 0 && <span className="sa-cwe-tag sa-cwe-tag-more mono">+{extra}</span>}
    </div>
  )
}

function CountCell({ value }) {
  return <span className="sa-fw-count mono">{value}</span>
}

function KevCell({ value }) {
  return value > 0
    ? <span className="sa-row-tag sa-row-tag-kev mono">{value}</span>
    : <span className="sa-fw-dim">—</span>
}

export default function FrameworkSection({ framework }) {
  const meta = FRAMEWORK_META[framework] || { title: framework, subtitle: '' }
  const [scope, setScope] = useState('all')
  const [severity, setSeverity] = useState('')
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
    fetchSecurityArchitectureFramework(framework, { scope, stack: scope === 'stack' ? stack : '', severity })
      .then(res => { if (!cancelled) setData(res) })
      .catch(err => {
        if (!cancelled) {
          setError(err)
          notifyApiError(err)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [framework, scope, stack, severity, reloadKey])

  const items = data?.items || []
  const isCategory = framework === 'owasp' || framework === 'stride'

  const columns = useMemo(() => {
    if (framework === 'cwe') {
      return [
        {
          id: 'cwe', label: 'Weakness', minWidth: 300,
          sortValue: (r) => r.cve_count,
          render: (r) => (
            <div className="sa-fw-title-cell">
              <span className="sa-row-title">{r.name}</span>
              <span className="sa-fw-id mono">{r.id}</span>
            </div>
          ),
        },
        { id: 'cve_count', label: 'CVEs', width: 80, sortValue: (r) => r.cve_count, render: (r) => <CountCell value={r.cve_count} /> },
        { id: 'kev_count', label: 'KEV', width: 70, sortValue: (r) => r.kev_count, render: (r) => <KevCell value={r.kev_count} /> },
        { id: 'owasp', label: 'OWASP', width: 110, render: (r) => <CweTags ids={r.owasp} limit={3} /> },
        { id: 'examples', label: 'Example CVEs', minWidth: 240, render: (r) => <ExampleCves items={r.example_cves} /> },
      ]
    }
    if (framework === 'capec') {
      return [
        {
          id: 'capec', label: 'Attack Pattern', minWidth: 300,
          sortValue: (r) => r.cve_count,
          render: (r) => (
            <div className="sa-fw-title-cell">
              <a className="sa-row-title sa-mitre-link" href={`https://capec.mitre.org/data/definitions/${r.id.replace('CAPEC-', '')}.html`} target="_blank" rel="noopener noreferrer">{r.name}</a>
              <span className="sa-fw-id mono">{r.id}</span>
            </div>
          ),
        },
        { id: 'cve_count', label: 'CVEs', width: 80, sortValue: (r) => r.cve_count, render: (r) => <CountCell value={r.cve_count} /> },
        { id: 'kev_count', label: 'KEV', width: 70, sortValue: (r) => r.kev_count, render: (r) => <KevCell value={r.kev_count} /> },
        { id: 'cwes', label: 'From CWEs', width: 150, render: (r) => <CweTags ids={r.cwe_ids} limit={4} /> },
        { id: 'examples', label: 'Example CVEs', minWidth: 240, render: (r) => <ExampleCves items={r.example_cves} /> },
      ]
    }
    // owasp | stride -- category rollups
    return [
      {
        id: 'category', label: framework === 'owasp' ? 'Category' : 'Threat Class', minWidth: 320,
        sortValue: (r) => r.cve_count,
        render: (r) => (
          <div className="sa-fw-title-cell">
            <span className="sa-row-title">{r.title}</span>
            <span className="sa-fw-cat-summary">{r.summary}</span>
          </div>
        ),
      },
      { id: 'cve_count', label: 'CVEs', width: 80, sortValue: (r) => r.cve_count, render: (r) => <CountCell value={r.cve_count} /> },
      { id: 'kev_count', label: 'KEV', width: 70, sortValue: (r) => r.kev_count, render: (r) => <KevCell value={r.kev_count} /> },
      { id: 'cwes', label: 'Matched CWEs', width: 160, render: (r) => <CweTags ids={r.cwe_ids} limit={4} /> },
      { id: 'examples', label: 'Example CVEs', minWidth: 220, render: (r) => <ExampleCves items={r.example_cves} /> },
    ]
  }, [framework])

  const total = data?.total_in_scope ?? 0
  const scopeUnavailable = data?.unavailable
  const emptyForScope = !loading && !error && total === 0

  return (
    <div className="sa-section">
      <div className="sa-section-head">
        <h2 className="sa-section-title mono">{meta.title}</h2>
        {data?.owasp_version && <span className="sa-fw-badge mono">OWASP {data.owasp_version}</span>}
        {data?.mapping === 'heuristic' && (
          <Tooltip text="STRIDE has no official 1:1 CWE mapping; this is a documented heuristic. Each row shows the CWEs behind it so you can judge the assignment.">
            <span className="sa-fw-badge sa-fw-badge-heuristic mono">heuristic mapping</span>
          </Tooltip>
        )}
      </div>
      <p className="sa-fw-subtitle">{meta.subtitle}</p>

      <div className="sa-scope-bar" role="group" aria-label="Scope">
        <span className="sa-subsection-label mono">SCOPE</span>
        {SCOPES.map(s => (
          <Tooltip key={s.id} text={s.help}>
            <button
              type="button"
              className={`sa-scope-btn mono${scope === s.id ? ' active' : ''}`}
              aria-pressed={scope === s.id}
              onClick={() => setScope(s.id)}
            >
              {s.label}
            </button>
          </Tooltip>
        ))}
        <span className="sa-scope-sep" aria-hidden="true" />
        <label className="sa-subsection-label mono" htmlFor={`sa-fw-sev-${framework}`}>SEVERITY</label>
        <select
          id={`sa-fw-sev-${framework}`}
          className="sa-fw-select mono"
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
        >
          {SEVERITIES.map(s => <option key={s || 'any'} value={s}>{s || 'Any'}</option>)}
        </select>
      </div>

      {scope === 'stack' && (
        <form
          className="sa-stack-filter"
          onSubmit={(e) => { e.preventDefault(); setStack(stackInput.trim()) }}
        >
          <label className="sa-subsection-label mono" htmlFor={`sa-fw-stack-${framework}`}>STACK TERMS</label>
          <input
            id={`sa-fw-stack-${framework}`}
            type="text"
            className="sa-stack-input mono"
            placeholder="e.g. apache, log4j, postgres — overrides your saved stack"
            value={stackInput}
            onChange={(e) => setStackInput(e.target.value)}
          />
          <button type="submit" className="admin-btn admin-btn-ghost mono">APPLY</button>
          {stack && (
            <button type="button" className="admin-btn admin-btn-ghost mono" onClick={() => { setStackInput(''); setStack('') }}>CLEAR</button>
          )}
        </form>
      )}

      {data && !scopeUnavailable && (
        <p className="sa-fw-meta mono">
          {total.toLocaleString()} CVE{total === 1 ? '' : 's'} in scope
          {data.cve_with_cwe != null && <> · {data.cve_with_cwe.toLocaleString()} with CWE data</>}
          {data.truncated && (
            <Tooltip text={`Aggregated over the ${data.sample_size.toLocaleString()} most decision-relevant CVEs (KEV + most recent) of ${total.toLocaleString()} in scope. Narrow the scope or severity for an exact count.`}>
              <span className="sa-fw-trunc"> · sampled {data.sample_size.toLocaleString()}</span>
            </Tooltip>
          )}
        </p>
      )}

      <AsyncState
        loading={loading}
        error={error}
        empty={Boolean(error) || emptyForScope}
        emptyTitle={
          error
            ? undefined
            : scopeUnavailable
              ? (data?.reason || 'This scope is unavailable.')
              : scope === 'stack'
                ? 'No CVEs match your stack in this scope yet.'
                : scope === 'watchlist'
                  ? 'Your watchlist has no CVEs in this scope yet.'
                  : 'No CVEs with CWE data in scope yet — ingest CVEs to populate the frameworks.'
        }
        onRetry={() => setReloadKey(k => k + 1)}
        skeleton={<div className="sa-skeleton-row" aria-hidden="true" />}
      >
        <ArchDataGrid
          gridId={`sa-framework-${framework}`}
          columns={columns}
          rows={items}
          rowKey={(r) => r.id}
          emptyMessage="No rows"
        />

        {isCategory || framework === 'capec' ? (
          data?.unmapped && data.unmapped.cve_count > 0 && (
            <div className="sa-fw-unmapped">
              <Tooltip text={data.unmapped.note}>
                <span className="sa-subsection-label mono">UNMAPPED</span>
              </Tooltip>
              <span className="sa-fw-unmapped-count mono">
                {data.unmapped.cve_count} CVE{data.unmapped.cve_count === 1 ? '' : 's'}
                {data.unmapped.kev_count > 0 && <> · {data.unmapped.kev_count} KEV</>}
              </span>
              <span className="sa-fw-unmapped-note">carry CWEs not mapped to this framework in the reference set — counted here so totals reconcile.</span>
              <ExampleCves items={data.unmapped.example_cves} />
            </div>
          )
        ) : null}
      </AsyncState>
    </div>
  )
}
