import { useState, useEffect, useCallback } from 'react'
import { adminApi } from '../../api.js'
import { Select } from '../../components/ui/index.js'
import AsyncSection from './shared/AsyncSection.jsx'
import HelpTip from './shared/HelpTip.jsx'

const EXPLORER_ACK_KEY = 'briefr-db-explorer-ack'

const PREVIEW_MAX = 120

function cellPreview(value) {
  if (value == null || value === '') return '—'
  const text = typeof value === 'object' ? JSON.stringify(value) : String(value)
  return text.length > PREVIEW_MAX ? `${text.slice(0, PREVIEW_MAX)}…` : text
}

export default function DbExplorerPanel({ toast }) {
  const [catalog, setCatalog] = useState(null)
  const [catalogError, setCatalogError] = useState(null)
  const [selectedTable, setSelectedTable] = useState('')
  const [filterColumn, setFilterColumn] = useState('')
  const [filterValue, setFilterValue] = useState('')
  const [rowsPayload, setRowsPayload] = useState(null)
  const [rowsError, setRowsError] = useState(null)
  const [rowsLoading, setRowsLoading] = useState(false)
  const [offset, setOffset] = useState(0)
  const [ack, setAck] = useState(() => {
    try { return sessionStorage.getItem(EXPLORER_ACK_KEY) === '1' } catch { return false }
  })

  const loadCatalog = useCallback(async () => {
    try {
      const res = await adminApi.get('/db-explorer/tables')
      setCatalog(await res.json())
      setCatalogError(null)
    } catch (e) {
      setCatalogError(e)
    }
  }, [])

  useEffect(() => { loadCatalog() }, [loadCatalog])

  const tableMeta = catalog?.tables?.find((t) => t.name === selectedTable) || null

  useEffect(() => {
    if (!tableMeta) {
      setFilterColumn('')
      return
    }
    if (tableMeta.required_filter) {
      setFilterColumn(tableMeta.required_filter)
      return
    }
    setFilterColumn((prev) => (
      prev && tableMeta.filter_columns.includes(prev)
        ? prev
        : (tableMeta.filter_columns[0] || '')
    ))
  }, [tableMeta])

  async function loadRows(nextOffset = 0) {
    if (!selectedTable) return
    if (tableMeta?.required_filter && !filterValue.trim()) {
      setRowsPayload(null)
      setRowsError({ message: `Enter a ${tableMeta.required_filter} filter before browsing this table.` })
      return
    }
    setRowsLoading(true)
    setRowsError(null)
    const params = new URLSearchParams({ limit: '50', offset: String(nextOffset) })
    if (filterColumn && filterValue.trim()) {
      params.set('filter_column', filterColumn)
      params.set('filter_value', filterValue.trim())
    }
    try {
      const res = await adminApi.get(`/db-explorer/tables/${encodeURIComponent(selectedTable)}/rows?${params}`)
      const data = await res.json()
      setRowsPayload(data)
      setOffset(nextOffset)
    } catch (e) {
      setRowsPayload(null)
      setRowsError(e)
      if (toast) toast(e.message || 'Browse failed', false)
    } finally {
      setRowsLoading(false)
    }
  }

  function dismissAck() {
    setAck(true)
    try { sessionStorage.setItem(EXPLORER_ACK_KEY, '1') } catch { /* unavailable */ }
  }

  return (
    <div className="admin-card" style={{ marginTop: '1rem' }}>
      <div className="admin-card-title">
        Table browser
        <HelpTip text="Read-only view of allowlisted PostgreSQL tables. Sensitive tables (users, sessions, webhook config, IOC cache) are hidden. No SQL is executed from your input — only pre-built parameterized queries." />
      </div>

      {!ack && (
        <div className="admin-callout admin-callout-amber" style={{ marginBottom: '0.75rem' }}>
          <span>
            <strong>Read-only explorer</strong> — browse allowlisted intel tables for debugging.
            Operator tables with credentials or IOC data are not listed. Browsing is audited; row bodies are not stored in the audit log.
            <button type="button" className="admin-btn admin-btn-ghost" style={{ marginLeft: '0.5rem' }} onClick={dismissAck}>
              Got it
            </button>
          </span>
        </div>
      )}

      <AsyncSection data={catalog} error={catalogError} onRetry={loadCatalog}>
        {() => (
          <div className="admin-filter-bar" style={{ flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <label style={{ fontSize: '0.75rem', color: 'var(--text3)' }}>
              Table
              <Select
                className="admin-input"
                style={{ marginLeft: '0.35rem', minWidth: 220 }}
                value={selectedTable}
                placeholder="Select table…"
                onChange={(v) => {
                  setSelectedTable(v)
                  setRowsPayload(null)
                  setRowsError(null)
                  setOffset(0)
                }}
                options={[
                  { value: '', label: 'Select table…' },
                  ...catalog.tables.map((t) => ({
                    value: t.name,
                    label: `${t.label} (${t.row_count.toLocaleString()} rows)${t.tier === 2 ? ' · masked' : ''}`,
                  })),
                ]}
              />
            </label>

            {tableMeta && tableMeta.filter_columns.length > 0 && (
              <>
                <label style={{ fontSize: '0.75rem', color: 'var(--text3)' }}>
                  Filter column
                  <Select
                    className="admin-input"
                    style={{ marginLeft: '0.35rem', minWidth: 140 }}
                    value={filterColumn}
                    disabled={Boolean(tableMeta.required_filter)}
                    onChange={setFilterColumn}
                    options={tableMeta.filter_columns.map((c) => ({ value: c, label: c }))}
                  />
                </label>
                <label style={{ fontSize: '0.75rem', color: 'var(--text3)' }}>
                  Filter value
                  <input
                    className="admin-input"
                    style={{ marginLeft: '0.35rem', minWidth: 200, fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}
                    placeholder={tableMeta.required_filter ? 'Required' : 'Optional'}
                    value={filterValue}
                    onChange={(e) => setFilterValue(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') loadRows(0) }}
                  />
                </label>
              </>
            )}

            <button
              type="button"
              className="admin-btn admin-btn-primary"
              disabled={!selectedTable || rowsLoading}
              onClick={() => loadRows(0)}
            >
              {rowsLoading ? <><span className="admin-spinner" /> Loading…</> : 'Browse rows'}
            </button>
          </div>
        )}
      </AsyncSection>

      {tableMeta?.required_filter && (
        <p style={{ fontSize: '0.72rem', color: 'var(--text3)', marginTop: '-0.25rem', marginBottom: '0.5rem' }}>
          <code>{tableMeta.name}</code> requires a <code>{tableMeta.required_filter}</code> filter (e.g. CVE-2024-1234) — full table scans are blocked.
        </p>
      )}

      {rowsError && !rowsLoading && (
        <div className="admin-callout admin-callout-amber" role="alert">
          {rowsError.message || 'Failed to load rows'}
          {rowsError.requestId && (
            <span style={{ marginLeft: '0.5rem', fontFamily: 'var(--font-mono)', fontSize: '0.7rem' }}>
              ref: {rowsError.requestId}
            </span>
          )}
          <button type="button" className="admin-btn admin-btn-ghost" style={{ marginLeft: '0.5rem' }} onClick={() => loadRows(offset)}>
            Retry
          </button>
        </div>
      )}

      {rowsPayload && (
        <>
          <div style={{ fontSize: '0.75rem', color: 'var(--text3)', marginBottom: '0.35rem' }}>
            Showing {rowsPayload.rows.length} of {rowsPayload.total.toLocaleString()} rows
            {rowsPayload.filter_column && rowsPayload.filter_value
              ? ` · ${rowsPayload.filter_column}=${rowsPayload.filter_value}`
              : ''}
            {rowsPayload.rows.some((r) => r._truncated) && ' · large fields truncated'}
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="admin-table">
              <thead>
                <tr>
                  {rowsPayload.columns.map((c) => <th key={c}>{c}</th>)}
                </tr>
              </thead>
              <tbody>
                {rowsPayload.rows.length === 0 && (
                  <tr><td colSpan={rowsPayload.columns.length} className="admin-empty">No rows match this filter</td></tr>
                )}
                {rowsPayload.rows.map((row, idx) => (
                  <tr key={idx}>
                    {rowsPayload.columns.map((c) => (
                      <td key={c} style={{ fontSize: '0.75rem', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={cellPreview(row[c])}>
                        {cellPreview(row[c])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="admin-action-bar" style={{ marginTop: '0.5rem' }}>
            <button
              type="button"
              className="admin-btn admin-btn-ghost"
              disabled={offset <= 0 || rowsLoading}
              onClick={() => loadRows(Math.max(0, offset - rowsPayload.limit))}
            >
              Previous
            </button>
            <button
              type="button"
              className="admin-btn admin-btn-ghost"
              disabled={!rowsPayload.has_more || rowsLoading}
              onClick={() => loadRows(offset + rowsPayload.limit)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  )
}
