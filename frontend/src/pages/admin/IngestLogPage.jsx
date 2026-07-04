import { Fragment, useState, useEffect, useRef } from 'react'
import { adminApi } from '../../api.js'

export default function IngestLogPage({ toast, onErrorCountChange, active = true, urlFilters = {} }) {
  const [logData, setLogData] = useState(null)
  const [level, setLevel] = useState(urlFilters.level || '')
  const [category, setCategory] = useState(urlFilters.category || '')
  const [loggerFilter, setLoggerFilter] = useState(urlFilters.logger || '')
  const [reqId, setReqId] = useState(urlFilters.requestId || '')
  const [limit, setLimit] = useState(100)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [expanded, setExpanded] = useState(() => new Set())
  const intervalRef = useRef(null)

  const logs = logData?.logs || []
  const knownLoggers = logData?.known_loggers || []
  const categories = logData?.categories || []

  useEffect(() => {
    if (urlFilters.level != null) setLevel(urlFilters.level)
    if (urlFilters.category != null) setCategory(urlFilters.category)
    if (urlFilters.logger != null) setLoggerFilter(urlFilters.logger)
    if (urlFilters.requestId != null) setReqId(urlFilters.requestId)
  }, [urlFilters.level, urlFilters.category, urlFilters.logger, urlFilters.requestId])

  async function loadLogs() {
    const params = new URLSearchParams({ limit })
    if (level) params.set('level', level)
    if (category) params.set('category', category)
    if (loggerFilter) params.set('logger', loggerFilter)
    if (reqId) params.set('request_id', reqId)
    try {
      const res = await adminApi.get(`/logs?${params}`)
      const data = await res.json()
      setLogData(data)
      if (onErrorCountChange) {
        const errorCount = (data.logs || []).filter(e => e.level === 'ERROR' || e.level === 'CRITICAL').length
        onErrorCountChange(errorCount)
      }
    } catch { }
  }

  useEffect(() => { loadLogs() }, [level, category, loggerFilter, reqId, limit])

  useEffect(() => {
    if (autoRefresh && active) {
      intervalRef.current = setInterval(loadLogs, 10000)
    } else {
      clearInterval(intervalRef.current)
    }
    return () => clearInterval(intervalRef.current)
  }, [autoRefresh, active, level, category, loggerFilter, reqId, limit])

  function exportLogs() {
    const lines = logs.map(e => JSON.stringify(e)).join('\n')
    const blob = new Blob([lines], { type: 'application/x-ndjson' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `briefr-logs-${new Date().toISOString().slice(0, 10)}.ndjson`
    a.click()
    URL.revokeObjectURL(url)
  }

  function rowStyle(entry) {
    if (entry.level === 'ERROR' || entry.level === 'CRITICAL') return { background: 'rgba(232,85,51,0.05)' }
    return {}
  }

  function toggleExpanded(key) {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  return (
    <div>
      <h1 className="admin-page-title">Application logs</h1>
      <p className="admin-page-subtitle">Live backend log stream, filterable by level/category/logger. Useful for tracing a specific request or recent error.</p>
      <div className="admin-filter-bar">
        <select className="admin-select" value={level} onChange={e => setLevel(e.target.value)}>
          <option value="">All levels</option>
          {['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <select className="admin-select" value={category} onChange={e => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="admin-select" value={loggerFilter} onChange={e => setLoggerFilter(e.target.value)}>
          <option value="">All loggers</option>
          {knownLoggers.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <input className="admin-input" placeholder="request_id…" value={reqId} onChange={e => setReqId(e.target.value)} style={{ minWidth: 160 }} />
        <select className="admin-select" value={limit} onChange={e => setLimit(Number(e.target.value))}>
          {[50, 100, 250, 500].map(n => <option key={n} value={n}>{n} entries</option>)}
        </select>
        <button className="admin-btn admin-btn-ghost" onClick={loadLogs}>Refresh</button>
        <button className="admin-btn admin-btn-ghost" onClick={exportLogs} title="Export as NDJSON">Export logs</button>
        <label className="admin-toggle-label">
          <div className="admin-toggle-wrap">
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
            <span className="admin-toggle-slider" />
          </div>
          Auto (10s)
        </label>
      </div>
      <div className="admin-card" style={{ padding: 0 }}>
        <table className="admin-table">
          <thead>
            <tr><th>TIMESTAMP</th><th>LEVEL</th><th>CATEGORY</th><th>LOGGER</th><th>MESSAGE</th><th>REQUEST ID</th></tr>
          </thead>
          <tbody>
            {logs.length === 0 && !logData && <tr><td colSpan={6} className="admin-empty">Loading…</td></tr>}
            {logs.length === 0 && logData && <tr><td colSpan={6} className="admin-empty">{level || category || loggerFilter || reqId ? 'No log entries match the current filters — try a broader level or clear the filters' : 'Log buffer is empty — backend activity will appear here once jobs run'}</td></tr>}
            {logs.map((entry) => {
              const hasDetail = Boolean(entry.exc_info)
              const entryKey = `${entry.ts}-${entry.logger}-${entry.request_id}-${entry.message}`
              const isExpanded = expanded.has(entryKey)
              return (
                <Fragment key={entryKey}>
                  <tr
                    style={{ ...rowStyle(entry), cursor: hasDetail ? 'pointer' : undefined }}
                    onClick={hasDetail ? () => toggleExpanded(entryKey) : undefined}
                    title={hasDetail ? 'Click for full traceback' : undefined}
                  >
                    <td className="mono" style={{ fontSize: '0.68rem', whiteSpace: 'nowrap' }}>{entry.ts}</td>
                    <td>
                      <span className={`level-badge level-${entry.level}`}>{entry.level}</span>
                    </td>
                    <td style={{ fontSize: '0.72rem', color: 'var(--text3)' }}>{entry.category || 'Application'}</td>
                    <td className="mono" style={{ fontSize: '0.68rem', color: 'var(--text3)' }}>{entry.logger}</td>
                    <td style={{ fontSize: '0.8rem', wordBreak: 'break-word', maxWidth: 480, color: entry.level === 'ERROR' || entry.level === 'CRITICAL' ? 'var(--red)' : undefined }}>
                      {hasDetail && <span className="mono" style={{ color: 'var(--text3)', marginRight: 6 }}>{isExpanded ? '▼' : '▶'}</span>}
                      {entry.message}
                    </td>
                    <td className="mono" style={{ fontSize: '0.68rem', color: 'var(--text3)' }}>{entry.request_id || ''}</td>
                  </tr>
                  {hasDetail && isExpanded && (
                    <tr>
                      <td colSpan={6} style={{ padding: 0 }}>
                        <pre
                          className="mono"
                          style={{
                            margin: 0,
                            padding: '10px 14px',
                            fontSize: '0.7rem',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            background: 'rgba(232,85,51,0.04)',
                            color: 'var(--text2)',
                            maxHeight: 400,
                            overflowY: 'auto',
                          }}
                        >
                          {entry.exc_info}
                        </pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
