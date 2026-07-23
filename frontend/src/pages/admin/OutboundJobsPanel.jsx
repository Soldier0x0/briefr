import { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'

import { adminApi } from '../../api.js'
import useVisibilityAwareInterval from '../../hooks/useVisibilityAwareInterval.js'
import { fmtIso } from './formatters.js'
import { outboundJobsEmptyMessage } from './outboundJobsCopy.js'
import AdminDataGrid from './shared/AdminDataGrid.jsx'
import AsyncSection from './shared/AsyncSection.jsx'
import HelpTip from './shared/HelpTip.jsx'
import OutboundJobStatusBadge from './shared/OutboundJobStatusBadge.jsx'

const POLL_MS = 15000

export default function OutboundJobsPanel() {
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [pinging, setPinging] = useState(false)
  const [pingMessage, setPingMessage] = useState('')
  const [pingError, setPingError] = useState(null)

  const loadJobs = useCallback(async ({ suppressLoading = false } = {}) => {
    if (!suppressLoading) setLoading(true)
    try {
      const { data } = await adminApi.listOutboundJobs(50)
      setPayload(data)
      setError(null)
    } catch (err) {
      setError({
        message: err?.message || 'Failed to load durable outbound jobs',
        requestId: err?.requestId || null,
      })
    } finally {
      if (!suppressLoading) setLoading(false)
    }
  }, [])

  const pingQueue = useCallback(async () => {
    setPinging(true)
    setPingMessage('')
    setPingError(null)
    try {
      const { data } = await adminApi.pingOutboundQueue()
      setPingMessage(data?.message || 'health_ping queued')
      await loadJobs({ suppressLoading: true })
    } catch (err) {
      setPingError({
        message: err?.message || 'Failed to ping durable outbound queue',
        requestId: err?.requestId || null,
      })
    } finally {
      setPinging(false)
    }
  }, [loadJobs])

  useEffect(() => {
    loadJobs()
  }, [loadJobs])

  useVisibilityAwareInterval(
    () => loadJobs({ suppressLoading: true }),
    POLL_MS,
    { enabled: Boolean(payload) },
  )

  const rows = payload?.jobs || []
  const emptyMessage = outboundJobsEmptyMessage({ enabled: Boolean(payload?.enabled) })
  const summary = payload
    ? `${payload.count ?? rows.length} job${(payload.count ?? rows.length) === 1 ? '' : 's'}`
    : ''

  const columns = useMemo(() => {
    const base = [
      {
        id: 'id',
        label: 'ID',
        defaultVisible: true,
        render: (row) => <span className="mono">{row.id ?? '—'}</span>,
      },
      {
        id: 'task',
        label: 'Task',
        defaultVisible: true,
        render: (row) => <span className="mono">{row.task ?? row.task_name ?? '—'}</span>,
      },
      {
        id: 'status',
        label: 'Status',
        defaultVisible: true,
        render: (row) => <OutboundJobStatusBadge status={row.status} />,
      },
      {
        id: 'attempts',
        label: 'Attempts',
        defaultVisible: true,
        render: (row) => <span className="mono">{row.attempts ?? '—'}</span>,
      },
      {
        id: 'scheduled_at',
        label: 'Scheduled',
        defaultVisible: true,
        render: (row) => (
          <span className="mono">
            {row.scheduled_at != null && row.scheduled_at !== '' ? fmtIso(row.scheduled_at) : '—'}
          </span>
        ),
      },
      {
        id: 'queueing_lock',
        label: 'Queueing lock',
        defaultVisible: true,
        render: (row) => <span className="mono">{row.queueing_lock || '—'}</span>,
      },
    ]

    const optional = [
      {
        id: 'queue',
        label: 'Queue',
        defaultVisible: true,
        field: 'queue',
        altField: 'queue_name',
      },
      {
        id: 'priority',
        label: 'Priority',
        defaultVisible: true,
        field: 'priority',
      },
      {
        id: 'lock',
        label: 'Lock',
        defaultVisible: true,
        field: 'lock',
      },
    ]

    const hasOptional = (field, altField) => rows.some((row) => {
      const value = row[field] ?? (altField ? row[altField] : undefined)
      return value != null && value !== ''
    })

    for (const col of optional) {
      if (!hasOptional(col.field, col.altField)) continue
      base.push({
        id: col.id,
        label: col.label,
        defaultVisible: col.defaultVisible,
        render: (row) => {
          const val = row[col.field] ?? (col.altField ? row[col.altField] : null)
          return <span className="mono">{val !== '' && val != null ? val : '—'}</span>
        },
      })
    }

    return base
  }, [rows])

  const sectionData = loading && !payload ? null : rows

  return (
    <div className="admin-card">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="admin-card-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          Durable outbound jobs
          <HelpTip text="PostgreSQL-backed Procrastinate queue rows — retries and scheduling survive process restarts. This is not the header API queue indicator, which only paces in-memory outbound HTTP calls and does not persist job history." />
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
          {summary ? (
            <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text3)' }}>
              {summary}
              {payload?.enabled === false ? ' · disabled' : ''}
            </span>
          ) : null}
          <button
            type="button"
            className="admin-btn admin-btn-ghost"
            style={{ fontSize: '0.75rem' }}
            disabled={loading || pinging || payload?.enabled === false}
            onClick={pingQueue}
          >
            {pinging ? 'Pinging...' : 'Ping queue'}
          </button>
          <button
            type="button"
            className="admin-btn admin-btn-ghost"
            style={{ fontSize: '0.75rem' }}
            disabled={loading}
            onClick={() => loadJobs()}
            aria-label="Refresh durable outbound jobs"
          >
            <RefreshCw size={12} style={{ marginRight: '0.35rem', verticalAlign: '-2px' }} aria-hidden="true" />
            Refresh
          </button>
        </div>
      </div>
      <p className="admin-page-subtitle" style={{ marginTop: '0.5rem' }}>
        Recent Procrastinate tasks from <code className="mono">procrastinate_jobs</code> (newest first).
        Enable with <code className="mono">PROCRASTINATE_ENABLED=1</code> and restart the backend.
      </p>
      {error && !payload ? (
        <div className="admin-callout admin-callout-red" role="alert">
          <span>
            {error.message}
            {error.requestId ? (
              <>
                {' '}
                <span className="mono">ref: {error.requestId}</span>
              </>
            ) : null}
          </span>
          <button type="button" className="admin-btn admin-btn-ghost" onClick={() => loadJobs()}>
            Retry
          </button>
        </div>
      ) : null}
      {pingMessage ? (
        <p className="admin-page-subtitle" role="status" style={{ marginBottom: '1rem' }}>
          {pingMessage}
        </p>
      ) : null}
      {pingError ? (
        <div className="admin-callout admin-callout-red" role="alert" style={{ marginBottom: '1rem' }}>
          <span>
            {pingError.message}
            {pingError.requestId ? (
              <>
                {' '}
                <span className="mono">ref: {pingError.requestId}</span>
              </>
            ) : null}
          </span>
        </div>
      ) : null}
      {error && payload ? (
        <div className="admin-callout admin-callout-amber" role="alert" style={{ marginBottom: '1rem' }}>
          <span>
            {error.message}
            {error.requestId ? (
              <>
                {' '}
                <span className="mono">ref: {error.requestId}</span>
              </>
            ) : null}
          </span>
          <button
            type="button"
            className="admin-btn admin-btn-ghost"
            onClick={() => loadJobs({ suppressLoading: true })}
          >
            Retry
          </button>
        </div>
      ) : null}
      {!(error && !payload) ? (
        <AsyncSection
          data={sectionData}
          emptyMessage={emptyMessage}
          onRetry={() => loadJobs()}
        >
          {(jobRows) => (
            <AdminDataGrid
              gridId="outbound-jobs"
              columns={columns}
              rows={jobRows}
              rowKey={(row) => String(row.id)}
              emptyMessage={emptyMessage}
            />
          )}
        </AsyncSection>
      ) : null}
    </div>
  )
}
