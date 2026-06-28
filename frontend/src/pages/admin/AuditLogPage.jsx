import { useState, useEffect, useRef } from 'react'
import { adminApi } from '../../api.js'
import { AUDIT_PREFIXES } from './constants.js'
import { fmtIsoMono } from './formatters.js'
import { auditActionLabel } from './catalog.js'

export default function AuditLogPage({ toast, urlFilters = {} }) {
  const [data, setData] = useState(null)
  const [activePrefix, setActivePrefix] = useState(urlFilters.actionPrefix || '')
  const [search, setSearch] = useState(urlFilters.q || '')
  const [offset, setOffset] = useState(0)
  const debounceRef = useRef(null)
  const limit = 100

  useEffect(() => {
    if (urlFilters.actionPrefix != null) setActivePrefix(urlFilters.actionPrefix)
    if (urlFilters.q != null) setSearch(urlFilters.q)
  }, [urlFilters.actionPrefix, urlFilters.q])

  useEffect(() => {
    if (urlFilters.actionPrefix != null || urlFilters.q != null) {
      load(urlFilters.actionPrefix || '', 0, urlFilters.q || '')
    }
  }, [urlFilters.actionPrefix, urlFilters.q])

  async function load(prefix = activePrefix, off = 0, q = search) {
    const params = new URLSearchParams({ limit, offset: off })
    if (prefix) params.set('action_prefix', prefix)
    if (q) params.set('q', q)
    try {
      const res = await adminApi.get(`/audit-log?${params}`)
      setData(await res.json())
      setOffset(off)
      setActivePrefix(prefix)
    } catch { }
  }

  useEffect(() => { load('', 0, '') }, [])

  function onSearchChange(value) {
    setSearch(value)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => load(activePrefix, 0, value), 300)
  }

  return (
    <div>
      <h1 className="admin-page-title">Audit log</h1>
      <p className="admin-page-subtitle">Searchable history of admin actions — who changed what, and when. Read-only.</p>
      <div className="admin-filter-bar" style={{ marginBottom: '0.75rem' }}>
        <div className="admin-filter-chips">
          <button className={`filter-chip ${activePrefix === '' ? 'active' : ''}`} onClick={() => load('', 0, search)}>All</button>
          {AUDIT_PREFIXES.map(p => (
            <button key={p} className={`filter-chip ${activePrefix === p + '.' ? 'active' : ''}`} onClick={() => load(p + '.', 0, search)}>
              {p}.*
            </button>
          ))}
        </div>
        <input
          className="admin-input"
          placeholder="Search action or target…"
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          style={{ marginLeft: 'auto', minWidth: 220 }}
        />
      </div>
      <div className="admin-card">
        <table className="admin-table">
          <thead><tr><th>ID</th><th>ACTOR</th><th>ACTION</th><th>TARGET</th><th>CREATED AT</th></tr></thead>
          <tbody>
            {data === null && <tr><td colSpan={5} className="admin-empty">Loading…</td></tr>}
            {data?.rows?.length === 0 && <tr><td colSpan={5} className="admin-empty">{search || activePrefix ? 'No audit events match your filters — try a different action type or clear the search' : 'No audit events recorded yet'}</td></tr>}
            {data?.rows?.map(r => (
              <tr key={r.id}>
                <td style={{ fontSize: '0.75rem' }}>{r.id}</td>
                <td className="mono" style={{ fontSize: '0.75rem' }}>{r.actor || '—'}</td>
                <td style={{ fontSize: '0.75rem' }}>{auditActionLabel(r.action)}</td>
                <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.8rem' }}>{r.target || '—'}</td>
                <td className="mono" style={{ fontSize: '0.7rem' }}>{fmtIsoMono(r.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && (
          <div className="admin-pagination">
            <button className="admin-btn admin-btn-ghost" disabled={offset === 0} onClick={() => load(activePrefix, Math.max(0, offset - limit), search)}>← Prev</button>
            <span style={{ color: 'var(--text3)', fontSize: '0.8125rem' }}>
              {offset + 1}–{Math.min(offset + limit, data.total)} of {data.total}
            </span>
            <button className="admin-btn admin-btn-ghost" disabled={offset + limit >= data.total} onClick={() => load(activePrefix, offset + limit, search)}>Load more →</button>
          </div>
        )}
      </div>
    </div>
  )
}
