import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { adminApi } from '../../api.js'
import { ingestLogUrl } from '../../utils/adminLinks.js'
import { formatMeteringActorLabel, jobLabel, termExplanation } from './catalog.js'
import { fmtIso } from './formatters.js'
import AdminDataGrid from './shared/AdminDataGrid.jsx'
import HelpTip from './shared/HelpTip.jsx'
import { Select } from '../../components/ui/index.js'

const HOUR_OPTIONS = [
  { value: '24', label: 'Last 24 hours' },
  { value: '48', label: 'Last 48 hours' },
  { value: '168', label: 'Last 7 days' },
]

const ACTOR_OPTIONS = [
  { value: '', label: 'All actors' },
  { value: 'user', label: 'User' },
  { value: 'job', label: 'Job' },
  { value: 'queue', label: 'Queue' },
  { value: 'unknown', label: 'Unknown' },
]

function destinationLabel(row) {
  const host = row.host || '—'
  const path = row.path_template || ''
  return path ? `${host}${path}` : host
}

function statusBadge(status) {
  if (status == null || status === '') return '—'
  const code = Number(status)
  if (!Number.isFinite(code)) return String(status)
  const ok = code >= 200 && code < 400
  return (
    <span className={`badge ${ok ? 'badge-ok' : 'badge-warn'}`} style={{ fontSize: '0.65rem' }}>
      {code}
    </span>
  )
}

function processCell(row) {
  if (row.job_id) {
    return <span className="mono">{jobLabel(row.job_id)}</span>
  }
  if (row.request_id) {
    return (
      <Link
        className="mono"
        to={ingestLogUrl({ requestId: row.request_id })}
        style={{ fontSize: '0.75rem' }}
      >
        Ingest log
      </Link>
    )
  }
  if (row.run_id) {
    return <span className="mono" style={{ color: 'var(--text3)' }}>{row.run_id}</span>
  }
  return '—'
}

export default function ApiCallAuditPanel({ sourceOptions = [] }) {
  const [open, setOpen] = useState(false)
  const [hours, setHours] = useState('24')
  const [source, setSource] = useState('')
  const [actorType, setActorType] = useState('')
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [exporting, setExporting] = useState(false)

  const loadEvents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({
        hours,
        limit: '100',
        offset: '0',
      })
      if (source) params.set('source', source)
      if (actorType) params.set('actor_type', actorType)
      const res = await adminApi.get(`/api-usage/events?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setPayload(await res.json())
    } catch (err) {
      setPayload(null)
      setError(err?.message || 'Audit trail unavailable')
    } finally {
      setLoading(false)
    }
  }, [hours, source, actorType])

  useEffect(() => {
    if (!open) return undefined
    loadEvents()
    return undefined
  }, [open, loadEvents])

  const sourceSelectOptions = useMemo(() => {
    const seen = new Set()
    const options = [{ value: '', label: 'All sources' }]
    for (const row of sourceOptions) {
      const key = row.source || row.name
      if (!key || seen.has(key)) continue
      seen.add(key)
      options.push({ value: key, label: key })
    }
    return options
  }, [sourceOptions])

  const columns = useMemo(() => [
    {
      id: 'ts',
      label: 'Time',
      defaultVisible: true,
      minWidth: 150,
      render: (row) => <span className="mono" style={{ fontSize: '0.75rem' }}>{fmtIso(row.ts)}</span>,
    },
    {
      id: 'source',
      label: 'Source',
      defaultVisible: true,
      width: 110,
      render: (row) => <span className="mono admin-config-value">{row.source || '—'}</span>,
    },
    {
      id: 'destination',
      label: 'Destination',
      defaultVisible: true,
      minWidth: 180,
      render: (row) => (
        <span className="mono" style={{ fontSize: '0.75rem' }} title={destinationLabel(row)}>
          {destinationLabel(row)}
        </span>
      ),
    },
    {
      id: 'status',
      label: 'Status',
      defaultVisible: true,
      width: 80,
      render: (row) => statusBadge(row.status),
    },
    {
      id: 'actor',
      label: 'Actor',
      defaultVisible: true,
      width: 120,
      render: (row) => (
        <span className="mono" style={{ fontSize: '0.75rem' }}>
          {formatMeteringActorLabel(row.actor_type)}
          {row.actor_id ? ` · ${row.actor_id}` : ''}
        </span>
      ),
    },
    {
      id: 'process',
      label: 'Process',
      defaultVisible: true,
      minWidth: 140,
      render: (row) => processCell(row),
    },
  ], [])

  async function exportCsv() {
    setExporting(true)
    try {
      const params = new URLSearchParams({ hours })
      if (source) params.set('source', source)
      if (actorType) params.set('actor_type', actorType)
      const res = await adminApi.get(`/api-usage/events/export?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'api-call-events.csv'
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err?.message || 'CSV export failed')
    } finally {
      setExporting(false)
    }
  }

  const greynoiseHelp = termExplanation('api_audit_greynoise')
  const showGreynoiseBreakdown = source === 'greynoise' && (payload?.actor_breakdown?.length > 0)

  return (
    <div className="admin-card" style={{ marginBottom: 'var(--space-4)' }}>
      <details
        className="admin-collapse api-audit-collapse"
        open={open}
        onToggle={(e) => setOpen(e.currentTarget.open)}
      >
        <summary className="config-section-header api-audit-summary">
          <div className="admin-card-title" style={{ margin: 0 }}>
            API call audit trail
            <HelpTip text={greynoiseHelp} />
          </div>
          <span className="config-section-chevron" aria-hidden>{open ? '▼' : '▶'}</span>
        </summary>

        <div className="admin-card-body" style={{ marginTop: '0.75rem' }}>
          <p className="admin-section-desc">
            Per-request outbound HTTP log (30-day retention in the database). Export CSV for longer
            analysis — up to 7 days per download.
          </p>

          <div className="api-audit-filters" role="group" aria-label="Audit trail filters">
            <label className="api-audit-filter">
              <span className="admin-config-key">Time range</span>
              <Select
                className="admin-select"
                value={hours}
                onChange={setHours}
                options={HOUR_OPTIONS}
              />
            </label>
            <label className="api-audit-filter">
              <span className="admin-config-key">Source</span>
              <Select
                className="admin-select"
                value={source}
                onChange={setSource}
                options={sourceSelectOptions}
              />
            </label>
            <label className="api-audit-filter">
              <span className="admin-config-key">Actor type</span>
              <Select
                className="admin-select"
                value={actorType}
                onChange={setActorType}
                options={ACTOR_OPTIONS}
              />
            </label>
            <div className="api-audit-filter-actions">
              <button
                type="button"
                className="admin-btn admin-btn-ghost"
                onClick={loadEvents}
                disabled={loading}
              >
                {loading ? 'Refreshing…' : 'Refresh'}
              </button>
              <button
                type="button"
                className="admin-btn admin-btn-primary"
                onClick={exportCsv}
                disabled={exporting}
                title="Download CSV for the selected filters (max 7 days)"
              >
                {exporting ? 'Exporting…' : 'Export CSV'}
              </button>
              <HelpTip text="Events are retained 30 days in the database. CSV export includes every matching row in the selected time window (up to 168 hours)." />
            </div>
          </div>

          {showGreynoiseBreakdown && (
            <div className="api-audit-greynoise-breakdown">
              <p className="metering-col-title">GREYNOISE BY ACTOR</p>
              <table className="metering-table">
                <thead>
                  <tr>
                    <th scope="col">Actor</th>
                    <th scope="col" className="metering-table-num">Calls</th>
                  </tr>
                </thead>
                <tbody>
                  {payload.actor_breakdown.map((row) => (
                    <tr key={row.actor_type}>
                      <td className="mono admin-config-value">{formatMeteringActorLabel(row.actor_type)}</td>
                      <td className="mono metering-table-num">{row.calls}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="admin-section-desc" style={{ marginTop: '0.5rem', marginBottom: 0 }}>
                User rows are opt-in IOC lookups; job rows are scheduled or background tasks.
              </p>
            </div>
          )}

          {loading && <p className="metering-empty mono">Loading audit events…</p>}
          {!loading && error && (
            <p className="metering-empty mono" style={{ color: 'var(--status-error)' }}>{error}</p>
          )}
          {!loading && !error && payload && (
            <>
              <p className="mono metering-empty" style={{ marginBottom: '0.5rem' }}>
                {payload.total?.toLocaleString() ?? 0} event{(payload.total === 1) ? '' : 's'}
                {payload.total > (payload.events?.length || 0)
                  ? ` · showing ${payload.events?.length || 0}`
                  : ''}
              </p>
              <AdminDataGrid
                gridId="api-call-audit"
                emptyMessage="No outbound API calls in this window"
                columns={columns}
                rows={payload.events || []}
                rowKey={(row, index) => `${row.ts}-${row.source}-${row.request_id || row.job_id || index}`}
              />
            </>
          )}
        </div>
      </details>
    </div>
  )
}
