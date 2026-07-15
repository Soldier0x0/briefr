import { Fragment, useState, useEffect, useRef } from 'react'
import { adminApi } from '../../api.js'
import { Select, Switch } from '../../components/ui/index.js'
import { AdminTableBodySkeletonRows } from './shared/AdminSkeletons.jsx'

const SEARCH_DEBOUNCE_MS = 300
const DETAIL_KEYS = new Set([
  'ts', 'level', 'logger', 'message', 'request_id', 'category', 'job_id', 'run_id', 'error_type',
])

export default function IngestLogPage({ toast, onErrorCountChange, active = true, urlFilters = {} }) {
  const [logData, setLogData] = useState(null)
  const [level, setLevel] = useState(urlFilters.level || '')
  const [category, setCategory] = useState(urlFilters.category || '')
  const [loggerFilter, setLoggerFilter] = useState(urlFilters.logger || '')
  const [reqId, setReqId] = useState(urlFilters.requestId || '')
  const [jobId, setJobId] = useState(urlFilters.jobId || '')
  const [runId, setRunId] = useState(urlFilters.runId || '')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [since, setSince] = useState('')
  const [until, setUntil] = useState('')
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
    if (urlFilters.jobId != null) setJobId(urlFilters.jobId)
    if (urlFilters.runId != null) setRunId(urlFilters.runId)
    setSearchInput('')
    setSearch('')
  }, [
    urlFilters.level,
    urlFilters.category,
    urlFilters.logger,
    urlFilters.requestId,
    urlFilters.jobId,
    urlFilters.runId,
  ])

  async function loadLogs() {
    const params = new URLSearchParams({ limit })
    if (level) params.set('level', level)
    if (category) params.set('category', category)
    if (loggerFilter) params.set('logger', loggerFilter)
    if (reqId) params.set('request_id', reqId)
    if (jobId) params.set('job_id', jobId)
    if (runId) params.set('run_id', runId)
    if (search) params.set('search', search)
    if (since) params.set('since', new Date(since).toISOString())
    if (until) params.set('until', new Date(until).toISOString())
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

  useEffect(() => { loadLogs() }, [level, category, loggerFilter, reqId, jobId, runId, search, since, until, limit])

  useEffect(() => {
    const handler = setTimeout(() => setSearch(searchInput.trim()), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(handler)
  }, [searchInput])

  useEffect(() => {
    if (autoRefresh && active) {
      intervalRef.current = setInterval(loadLogs, 10000)
    } else {
      clearInterval(intervalRef.current)
    }
    return () => clearInterval(intervalRef.current)
  }, [autoRefresh, active, level, category, loggerFilter, reqId, jobId, runId, search, since, until, limit])

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

  function entryExtras(entry) {
    return Object.fromEntries(
      Object.entries(entry).filter(([k, v]) => !DETAIL_KEYS.has(k) && v != null && v !== ''),
    )
  }

  function hasDetail(entry) {
    return Boolean(entry.exc_info) || Object.keys(entryExtras(entry)).length > 0
  }

  function detailText(entry) {
    const extras = entryExtras(entry)
    const parts = []
    if (Object.keys(extras).length > 0) {
      parts.push(JSON.stringify(extras, null, 2))
    }
    if (entry.exc_info) {
      parts.push(entry.exc_info)
    }
    return parts.join('\n\n')
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
      <p className="admin-page-subtitle">Live backend log stream, filterable by level, category, job, or request. Expand rows for tracebacks and structured fields.</p>
      <div className="admin-filter-bar">
        <input
          className="admin-input"
          placeholder="Search message / traceback…"
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          style={{ minWidth: 220 }}
        />
        <Select
          className="admin-select"
          value={level}
          onChange={setLevel}
          options={[
            { value: '', label: 'All levels' },
            ...['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].map(l => ({ value: l, label: l })),
          ]}
        />
        <Select
          className="admin-select"
          value={category}
          onChange={setCategory}
          options={[
            { value: '', label: 'All categories' },
            ...categories.map(c => ({ value: c, label: c })),
          ]}
        />
        <Select
          className="admin-select"
          value={loggerFilter}
          onChange={setLoggerFilter}
          options={[
            { value: '', label: 'All loggers' },
            ...knownLoggers.map(l => ({ value: l, label: l })),
          ]}
        />
        <input className="admin-input" placeholder="job_id…" value={jobId} onChange={e => setJobId(e.target.value)} style={{ minWidth: 140 }} />
        <input className="admin-input" placeholder="run_id…" value={runId} onChange={e => setRunId(e.target.value)} style={{ minWidth: 120 }} />
        <input className="admin-input" placeholder="request_id…" value={reqId} onChange={e => setReqId(e.target.value)} style={{ minWidth: 160 }} />
        <input
          className="admin-input"
          type="datetime-local"
          value={since}
          onChange={e => setSince(e.target.value)}
          title="Only entries at or after this time (local, converted to UTC)"
          aria-label="From time"
        />
        <input
          className="admin-input"
          type="datetime-local"
          value={until}
          onChange={e => setUntil(e.target.value)}
          title="Only entries at or before this time (local, converted to UTC)"
          aria-label="To time"
        />
        <Select
          className="admin-select"
          value={String(limit)}
          onChange={(v) => setLimit(Number(v))}
          options={[50, 100, 250, 500].map(n => ({ value: String(n), label: `${n} entries` }))}
        />
        <button className="admin-btn admin-btn-ghost" onClick={loadLogs}>Refresh</button>
        <button className="admin-btn admin-btn-ghost" onClick={exportLogs} title="Export as NDJSON">Export logs</button>
        <Switch
          id="ingest-log-auto-refresh"
          checked={autoRefresh}
          onCheckedChange={setAutoRefresh}
          label="Auto (10s)"
          className="admin-ingest-auto-refresh"
        />
      </div>
      <div className="admin-card" style={{ padding: 0 }}>
        <table className="admin-table">
          <thead>
            <tr><th>TIMESTAMP</th><th>LEVEL</th><th>CATEGORY</th><th>LOGGER</th><th>MESSAGE</th><th>JOB</th><th>RUN</th><th>REQUEST ID</th></tr>
          </thead>
          <tbody>
            {logs.length === 0 && !logData && <AdminTableBodySkeletonRows rows={8} cols={8} />}
            {logs.length === 0 && logData && <tr><td colSpan={8} className="admin-empty">{level || category || loggerFilter || reqId || jobId || runId || since || until ? 'No log entries match the current filters — try a broader level, wider time range, or clear the filters' : 'Log buffer is empty — backend activity will appear here once jobs run'}</td></tr>}
            {logs.map((entry) => {
              const expandable = hasDetail(entry)
              const entryKey = `${entry.ts}-${entry.logger}-${entry.request_id}-${entry.job_id || ''}-${entry.message}`
              const isExpanded = expanded.has(entryKey)
              return (
                <Fragment key={entryKey}>
                  <tr
                    style={{ ...rowStyle(entry), cursor: expandable ? 'pointer' : undefined }}
                    onClick={expandable ? () => toggleExpanded(entryKey) : undefined}
                    title={expandable ? 'Click for structured detail' : undefined}
                  >
                    <td className="mono" style={{ fontSize: '0.68rem', whiteSpace: 'nowrap' }}>{entry.ts}</td>
                    <td>
                      <span className={`level-badge level-${entry.level}`}>{entry.level}</span>
                    </td>
                    <td style={{ fontSize: '0.72rem', color: 'var(--text3)' }}>{entry.category || 'Application'}</td>
                    <td className="mono" style={{ fontSize: '0.68rem', color: 'var(--text3)' }}>{entry.logger}</td>
                    <td style={{ fontSize: '0.8rem', wordBreak: 'break-word', maxWidth: 420, color: entry.level === 'ERROR' || entry.level === 'CRITICAL' ? 'var(--red)' : undefined }}>
                      {expandable && <span className="mono" style={{ color: 'var(--text3)', marginRight: 6 }}>{isExpanded ? '▼' : '▶'}</span>}
                      {entry.message}
                    </td>
                    <td className="mono" style={{ fontSize: '0.68rem', color: 'var(--text3)' }}>{entry.job_id || ''}</td>
                    <td className="mono" style={{ fontSize: '0.68rem', color: 'var(--text3)' }}>{entry.run_id || ''}</td>
                    <td className="mono" style={{ fontSize: '0.68rem', color: 'var(--text3)' }}>{entry.request_id || ''}</td>
                  </tr>
                  {expandable && isExpanded && (
                    <tr>
                      <td colSpan={8} style={{ padding: 0 }}>
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
                          {detailText(entry)}
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
