import { useState, useEffect, useRef } from 'react'
import { adminApi } from '../../api.js'

export default function IngestLogPage({ toast, onErrorCountChange }) {
  const [logData, setLogData] = useState(null)
  const [level, setLevel] = useState('')
  const [loggerFilter, setLoggerFilter] = useState('')
  const [reqId, setReqId] = useState('')
  const [limit, setLimit] = useState(100)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const intervalRef = useRef(null)

  const logs = logData?.logs || []
  const knownLoggers = logData?.known_loggers || []

  async function loadLogs() {
    const params = new URLSearchParams({ limit })
    if (level) params.set('level', level)
    if (loggerFilter) params.set('logger', loggerFilter)
    if (reqId) params.set('request_id', reqId)
    try {
      const res = await adminApi.get(`/logs?${params}`)
      const data = await res.json()
      setLogData(data)
      // Count errors for sidebar badge
      if (onErrorCountChange) {
        const errorCount = (data.logs || []).filter(e => e.level === 'ERROR' || e.level === 'CRITICAL').length
        onErrorCountChange(errorCount)
      }
    } catch { }
  }

  useEffect(() => { loadLogs() }, [level, loggerFilter, reqId, limit])

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(loadLogs, 10000)
    } else {
      clearInterval(intervalRef.current)
    }
    return () => clearInterval(intervalRef.current)
  }, [autoRefresh, level, loggerFilter, reqId, limit])

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

  return (
    <div>
      <h1 className="admin-page-title">Ingest log</h1>
      <div className="admin-filter-bar">
        <select className="admin-select" value={level} onChange={e => setLevel(e.target.value)}>
          <option value="">All levels</option>
          {['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].map(l => <option key={l} value={l}>{l}</option>)}
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
            <tr><th>TIMESTAMP</th><th>LEVEL</th><th>LOGGER</th><th>MESSAGE</th><th>REQUEST ID</th></tr>
          </thead>
          <tbody>
            {logs.length === 0 && !logData && <tr><td colSpan={5} className="admin-empty">Loading…</td></tr>}
            {logs.length === 0 && logData && <tr><td colSpan={5} className="admin-empty">No logs in buffer</td></tr>}
            {logs.map((entry, i) => (
              <tr key={i} style={rowStyle(entry)}>
                <td className="mono" style={{ fontSize: '0.68rem', whiteSpace: 'nowrap' }}>{entry.ts}</td>
                <td>
                  <span className={`level-badge level-${entry.level}`}>{entry.level}</span>
                </td>
                <td className="mono" style={{ fontSize: '0.68rem', color: 'var(--text3)' }}>{entry.logger}</td>
                <td style={{ fontSize: '0.8rem', wordBreak: 'break-word', maxWidth: 480, color: entry.level === 'ERROR' || entry.level === 'CRITICAL' ? 'var(--red)' : undefined }}>
                  {entry.message}
                </td>
                <td className="mono" style={{ fontSize: '0.68rem', color: 'var(--text3)' }}>{entry.request_id || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
