import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { adminApi } from '../../api.js'
import { AlertDialog, Button, Modal, Select } from '../../components/ui/index.js'
import { fmtIso } from './formatters.js'
import AsyncSection from './shared/AsyncSection.jsx'
import HelpTip from './shared/HelpTip.jsx'
import StatCard from './shared/StatCard.jsx'
import { CIRCUIT_UI, LLM_ERROR_LABELS } from './circuitLabels.js'
import { activityRowHasPayload } from './aiOperationsActivityActions.js'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'providers', label: 'Providers' },
  { id: 'models', label: 'Models' },
  { id: 'usage', label: 'Usage' },
  { id: 'activity', label: 'Activity' },
]

const TASK_LABELS = {
  product_extraction: 'Product extraction',
  pdf_summary: 'PDF summary',
  detection_context: 'Detection context',
}

const ERROR_CLASS_LABELS = LLM_ERROR_LABELS
const PAYLOAD_PRE_STYLE = {
  margin: 0,
  border: '1px solid var(--border)',
  background: 'var(--surface-sunken)',
  borderRadius: 'var(--radius-md)',
  padding: 'var(--space-3)',
  maxHeight: '18rem',
  overflow: 'auto',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  fontFamily: 'var(--admin-mono)',
  fontSize: 'var(--type-meta, 0.75rem)',
  lineHeight: 1.45,
}

function formatErrorWithRef(error) {
  const message = String(error?.message || error || 'Request failed')
  return error?.requestId ? `${message} (ref: ${error.requestId})` : message
}

function pct(rate) {
  if (rate == null || Number.isNaN(rate)) return '—'
  return `${Math.round(rate * 100)}%`
}

function failRateTone(rate, attempts = 0) {
  if (!attempts || rate == null || Number.isNaN(rate)) return undefined
  if (rate >= 0.5) return 'color-red'
  if (rate >= 0.2) return 'color-amber'
  return undefined
}

function successBadge(success) {
  const ok = success === true || success === 1
  return (
    <span className={`badge ${ok ? 'badge-ok' : 'badge-error'}`}>
      {ok ? 'ok' : 'fail'}
    </span>
  )
}

function resultCell(row) {
  const ok = row.success === true || row.success === 1
  if (ok) return successBadge(true)

  if (row.error_class === 'circuit_open') {
    return (
      <span className="admin-result-cell">
        <span className="badge badge-muted">skipped</span>
        <span className="admin-result-reason">{ERROR_CLASS_LABELS.circuit_open}</span>
      </span>
    )
  }

  const reason = row.error_class
    ? (ERROR_CLASS_LABELS[row.error_class] || row.error_class.replace(/_/g, ' '))
    : null

  return (
    <span className="admin-result-cell">
      {successBadge(false)}
      {reason && <span className="admin-result-reason">{reason}</span>}
      {row.fallback_from_provider && (
        <span className="admin-result-fallback">
          fallback from {row.fallback_from_provider}
        </span>
      )}
    </span>
  )
}

function providerStatus(p) {
  if (!p.configured) return { label: 'No key', className: 'badge-muted' }
  if (p.circuit_open) return { label: CIRCUIT_UI.pausedProvider, className: 'badge-error' }
  if ((p.consecutive_failures || 0) > 0 || p.last_error) {
    return { label: CIRCUIT_UI.unstable, className: 'badge-warn' }
  }
  return { label: 'Healthy', className: 'badge-ok' }
}

function RetrievalHealthPanel({ health, loading, error, onRetry }) {
  if (loading && !health) {
    return (
      <div className="admin-card" style={{ marginBottom: 'var(--space-4)' }}>
        <div className="admin-card-title">Retrieval health</div>
        <p className="admin-muted mono">Loading…</p>
      </div>
    )
  }
  if (error && !health) {
    return (
      <div className="admin-card" style={{ marginBottom: 'var(--space-4)' }}>
        <div className="admin-card-title">Retrieval health</div>
        <p className="admin-muted">
          Could not load retrieval health
          {error?.requestId ? ` (ref: ${error.requestId})` : ''}.
          {' '}
          <button type="button" className="admin-btn admin-btn-ghost" onClick={onRetry}>Retry</button>
        </p>
      </div>
    )
  }
  if (!health) return null

  const counts = health.counts || {}
  const pending = health.pending || {}
  const last = health.last_backfill || {}
  const ingestTail = health.last_ingest_tail || {}
  const degraded = health.degraded

  return (
    <div className="admin-card" style={{ marginBottom: 'var(--space-4)' }}>
      <div className="admin-card-title">
        Retrieval health
        <HelpTip text="Live embeddings index used by hybrid search. Counts are from the embeddings table for the active model. Pending = missing or migrated placeholders only (hash-drift is handled by scheduled backfill)." />
      </div>
      {degraded?.reason && (
        <div className="admin-callout admin-callout-amber" style={{ marginBottom: 'var(--space-3)' }}>
          Degraded: {degraded.reason.replace(/_/g, ' ')}
          {degraded.reason === 'disabled' && ' — turn on EMBEDDINGS_ENABLED to use hybrid search.'}
          {degraded.reason === 'cold_index' && ' — run Rebuild search index on Scheduler.'}
          {degraded.reason === 'no_vector_extension' && ' — Postgres needs pgvector (vector extension).'}
        </div>
      )}
      {ingestTail.had_error && (
        <div className="admin-callout admin-callout-amber" style={{ marginBottom: 'var(--space-3)' }}>
          Auto-on-ingest last error
          {ingestTail.last_run_utc ? ` (${fmtIso(ingestTail.last_run_utc)})` : ''}
          {ingestTail.error_message ? `: ${String(ingestTail.error_message).slice(0, 160)}` : ''}
        </div>
      )}
      <div className="admin-stat-grid" style={{ marginBottom: 'var(--space-3)' }}>
        <StatCard label="Enabled" value={health.embeddings_enabled ? 'yes' : 'no'} />
        <StatCard label="Auto on ingest" value={health.auto_on_ingest ? 'yes' : 'no'} />
        <StatCard label="Extension" value={health.extension_vector || '—'} />
        <StatCard label="Index rows" value={counts.total ?? 0} />
      </div>
      <table className="admin-table">
        <thead>
          <tr>
            <th>Entity</th>
            <th>Indexed</th>
            <th>Pending (missing/migrated)</th>
          </tr>
        </thead>
        <tbody>
          {['cve', 'technique', 'campaign'].map((et) => (
            <tr key={et}>
              <td className="mono">{et}</td>
              <td>{counts[et] ?? 0}</td>
              <td>{pending[et] ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="admin-muted mono" style={{ marginTop: 'var(--space-3)', marginBottom: 0 }}>
        Model: {health.model || '—'}
        {' · '}
        Last backfill: {last.last_run_utc ? fmtIso(last.last_run_utc) : 'never'}
        {last.records_upserted != null ? ` (${last.records_upserted} records)` : ''}
        {last.had_error ? ' · error' : ''}
        {' · '}
        Ingest tail: {ingestTail.last_run_utc ? fmtIso(ingestTail.last_run_utc) : 'never'}
        {ingestTail.embedded != null ? ` (${ingestTail.embedded} embedded)` : ''}
        {' · '}
        <Link to="/admin?p=scheduler" style={{ color: 'var(--accent)' }}>Scheduler</Link>
      </p>
    </div>
  )
}

function OverviewTab({ overview, setPage, retrievalHealth, retrievalLoading, retrievalError, onRetryRetrieval }) {
  const u24 = overview?.usage?.['24h'] || {}
  const circuits = overview?.active_circuit_count || 0
  const configured = overview?.configured_provider_count || 0
  const failRate = u24.failure_rate
  const apiAttempts = u24.api_attempts ?? Math.max(0, (u24.total ?? 0) - (u24.skipped_cooldown ?? 0))
  const failTone = failRateTone(failRate, apiAttempts)
  const skippedCooldown = u24.skipped_cooldown ?? 0

  return (
    <div>
      <RetrievalHealthPanel
        health={retrievalHealth}
        loading={retrievalLoading}
        error={retrievalError}
        onRetry={onRetryRetrieval}
      />
      {failTone && apiAttempts > 0 && (
        <div
          className={`admin-callout ${failRate >= 0.5 ? 'admin-callout-red' : 'admin-callout-amber'}`}          role="alert"
          style={{ marginBottom: '1rem' }}
        >
          LLM API error rate is {pct(failRate)} in the last 24 hours ({u24.failures ?? 0} of {apiAttempts} API attempts).
          {skippedCooldown > 0 ? ` ${skippedCooldown} cooldown skip${skippedCooldown === 1 ? '' : 's'} excluded.` : ''}
          {' '}Review the Providers tab for paused providers and API keys.
        </div>
      )}
      <div className="admin-stat-grid" style={{ marginBottom: '1rem' }}>
        <StatCard
          label="Providers configured"
          value={configured}
          subLabel={overview?.any_provider_configured ? 'At least one LLM key set' : 'No LLM keys — templates only'}
          colorClass={overview?.any_provider_configured ? 'color-green' : 'color-amber'}
        />
        <StatCard
          label="24h API attempts"
          value={apiAttempts}
          subLabel={`${u24.failures ?? 0} API errors · ${pct(failRate)} error rate`}
          colorClass={failTone}
          subLabelTitle={failTone ? 'Elevated LLM API error rate in the last 24 hours (cooldown skips excluded)' : undefined}
        />
        <StatCard
          label={CIRCUIT_UI.providersInCooldown}
          value={circuits}
          colorClass={circuits > 0 ? 'color-red' : 'color-green'}
          subLabel={circuits > 0 ? CIRCUIT_UI.oneOrMorePaused : CIRCUIT_UI.nonePaused}
        />
        <StatCard
          label="Recorded operations"
          value={overview?.total_operations ?? 0}
          subLabel={overview?.recording_enabled ? 'Recording enabled' : 'Recording disabled'}
          subLabelTitle={
            overview?.recording_enabled
              ? 'AI_OPERATIONS_RECORD is enabled — call metadata is persisted'
              : 'Set AI_OPERATIONS_RECORD to persist LLM call metadata'
          }
        />
      </div>

      <div className="admin-card" style={{ marginBottom: '1rem' }}>
        <div className="admin-card-title">
          Features
          <HelpTip text="Scheduler ML flags and on-demand PDF summary availability. Secrets live on API keys & config." />
        </div>
        <table className="admin-table">
          <thead>
            <tr>
              <th>Feature</th>
              <th>Trigger</th>
              <th>Enabled</th>
              <th>LLM available</th>
            </tr>
          </thead>
          <tbody>
            {overview?.features && Object.entries(overview.features).map(([key, feat]) => (
              <tr key={key}>
                <td>{feat.label}</td>
                <td style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{feat.trigger}</td>
                <td>
                  {'enabled' in feat
                    ? <span className={`badge ${feat.enabled ? 'badge-ok' : 'badge-muted'}`}>{feat.enabled ? 'yes' : 'no'}</span>
                    : <span className="badge badge-muted">n/a</span>}
                </td>
                <td>
                  {'available' in feat && (
                    <span className={`badge ${feat.available ? 'badge-ok' : 'badge-warn'}`}>
                      {feat.available ? 'yes' : 'no'}
                    </span>
                  )}
                  {'vector_count' in feat && (
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      {feat.enabled
                        ? `${feat.vector_count ?? 0} indexed`
                        : 'off'}
                      {feat.enabled && feat.legacy_cve_embeddings != null && (
                        <span title="Legacy cve_embeddings row count">
                          {` · legacy ${feat.legacy_cve_embeddings}`}
                        </span>
                      )}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="admin-callout">
        API keys and model env vars are edited on{' '}
        <button
          type="button"
          className="admin-btn admin-btn-ghost"
          style={{ display: 'inline', padding: 0, fontSize: 'inherit', verticalAlign: 'baseline' }}
          onClick={() => setPage?.('apikeys')}
        >
          API keys &amp; config
        </button>
        . This page is read-only observability — no prompt text is stored.
      </div>
    </div>
  )
}

function ProvidersTab({ providers }) {
  const rows = providers?.providers || []
  return (
    <div className="admin-card">
      <div className="admin-card-title">
        Provider health
        <HelpTip text="Pause state from the shared outbound client. Providers without traffic yet show empty health until first call." />
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table className="admin-table">
          <thead>
            <tr>
              <th>Provider</th>
              <th>Key</th>
              <th>Status</th>
              <th>Last success</th>
              <th>Last error</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(p => {
              const st = providerStatus(p)
              return (
                <tr key={p.provider}>
                  <td style={{ fontFamily: 'monospace' }}>{p.provider}</td>
                  <td>
                    <span className={`badge ${p.configured ? 'badge-ok' : 'badge-muted'}`}>
                      {p.configured ? 'configured' : 'missing'}
                    </span>
                    <span className="admin-env-key mono" title={p.env_key}>{p.env_key}</span>
                  </td>
                  <td><span className={`badge ${st.className}`}>{st.label}</span></td>
                  <td style={{ fontSize: '0.78rem' }}>{p.last_success ? fmtIso(p.last_success) : '—'}</td>
                  <td style={{ fontSize: '0.78rem', color: 'var(--amber)', maxWidth: '280px', wordBreak: 'break-all' }}>
                    {p.last_error ? p.last_error.slice(0, 120) : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ModelsTab({ models }) {
  const tasks = models?.tasks || {}
  return (
    <div className="admin-card">
      <div className="admin-card-title">
        Failover chains
        <HelpTip text="Read-only catalog from model_catalog.py. Order is failover priority, not round-robin." />
      </div>
      {Object.entries(tasks).map(([task, steps]) => (
        <div key={task} style={{ marginBottom: '1rem' }}>
          <div style={{ fontFamily: 'monospace', fontSize: '0.8rem', marginBottom: '0.35rem', color: 'var(--text2)' }}>
            {TASK_LABELS[task] || task}
          </div>
          <table className="admin-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Provider</th>
                <th>Model</th>
              </tr>
            </thead>
            <tbody>
              {(steps || []).map(step => (
                <tr key={`${task}-${step.order}`}>
                  <td>{step.order}</td>
                  <td>{step.provider}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{step.model}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}

function UsageTab({ overview }) {
  const windows = [
    { key: '24h', label: 'Last 24 hours' },
    { key: '7d', label: 'Last 7 days' },
  ]
  return (
    <div>
      {windows.map(({ key, label }) => {
        const u = overview?.usage?.[key] || {}
        return (
          <div key={key} className="admin-card" style={{ marginBottom: '1rem' }}>
            <div className="admin-card-title">{label}</div>
            <div className="admin-stat-grid" style={{ marginBottom: '0.75rem' }}>
              <StatCard label="Total attempts" value={u.total ?? 0} />
              <StatCard label="Successes" value={u.successes ?? 0} colorClass="color-green" />
              <StatCard
                label="Failures"
                value={u.failures ?? 0}
                colorClass={(u.failures ?? 0) > 0 ? 'color-amber' : undefined}
              />
              <StatCard
                label="Fail rate"
                value={pct(u.failure_rate)}
                colorClass={failRateTone(u.failure_rate, u.total ?? 0)}
              />
              <StatCard label="Failover wins" value={u.fallback_successes ?? 0} subLabel="Succeeded after prior provider failed" />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text3)', marginBottom: '0.35rem' }}>By provider</div>
                <table className="admin-table">
                  <thead><tr><th>Provider</th><th>Total</th><th>OK</th></tr></thead>
                  <tbody>
                    {(u.by_provider || []).length === 0
                      ? <tr><td colSpan={3} style={{ color: 'var(--text3)' }}>No operations in window</td></tr>
                      : u.by_provider.map(row => (
                        <tr key={row.provider}>
                          <td>{row.provider}</td>
                          <td>{row.total}</td>
                          <td>{row.successes}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text3)', marginBottom: '0.35rem' }}>By task</div>
                <table className="admin-table">
                  <thead><tr><th>Task</th><th>Total</th><th>OK</th></tr></thead>
                  <tbody>
                    {(u.by_task || []).length === 0
                      ? <tr><td colSpan={3} style={{ color: 'var(--text3)' }}>No operations in window</td></tr>
                      : u.by_task.map(row => (
                        <tr key={row.task_class}>
                          <td>{TASK_LABELS[row.task_class] || row.task_class}</td>
                          <td>{row.total}</td>
                          <td>{row.successes}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
            {u.tokens_recorded ? (
              <p style={{ fontSize: '0.75rem', color: 'var(--text3)', marginTop: '0.75rem' }}>
                Tokens: {(u.total_tokens ?? 0).toLocaleString()} total
                {' '}({(u.input_tokens ?? 0).toLocaleString()} in · {(u.output_tokens ?? 0).toLocaleString()} out).
                {' '}Only providers that return usage are counted; cost is not estimated.
              </p>
            ) : (
              <p style={{ fontSize: '0.75rem', color: 'var(--text3)', marginTop: '0.75rem' }}>
                Token counts appear once a provider that reports usage runs in this window — request/latency/fallback metrics only so far.
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}

function ActivityTab({ toast, providerOptions }) {
  const [rows, setRows] = useState(null)
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [taskFilter, setTaskFilter] = useState('')
  const [providerFilter, setProviderFilter] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [payloadOpen, setPayloadOpen] = useState(false)
  const [payloadLoading, setPayloadLoading] = useState(false)
  const [payloadError, setPayloadError] = useState(null)
  const [payloadData, setPayloadData] = useState(null)
  const [retryTarget, setRetryTarget] = useState(null)
  const [retryingOperationId, setRetryingOperationId] = useState('')
  const limit = 50

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
      if (taskFilter) params.set('task_class', taskFilter)
      if (providerFilter) params.set('provider', providerFilter)
      const { data } = await adminApi.getJson(`/ai/operations/activity?${params}`)
      setRows(data.rows || [])
      setTotal(data.total || 0)
      setError(null)
    } catch (e) {
      setError(e)
      toast?.(formatErrorWithRef(e), false)
    } finally {
      setLoading(false)
    }
  }, [offset, taskFilter, providerFilter, toast])

  useEffect(() => { load() }, [load])

  async function openPayloadFor(operationId) {
    setPayloadOpen(true)
    setPayloadLoading(true)
    setPayloadError(null)
    setPayloadData(null)
    try {
      const { data } = await adminApi.getJson(`/ai/operations/${encodeURIComponent(operationId)}/payload`)
      setPayloadData(data)
    } catch (e) {
      setPayloadError(e)
      toast?.(formatErrorWithRef(e), false)
    } finally {
      setPayloadLoading(false)
    }
  }

  function closePayload() {
    setPayloadOpen(false)
    setPayloadLoading(false)
    setPayloadError(null)
    setPayloadData(null)
  }

  function openRetryDialog(row) {
    setRetryTarget({
      operationId: row.operation_id,
      taskClass: row.task_class,
    })
  }

  async function confirmRetryOperation() {
    if (!retryTarget) return
    const operationId = retryTarget.operationId
    setRetryingOperationId(operationId)
    setRetryTarget(null)
    try {
      const { data } = await adminApi.postJson(`/ai/operations/${encodeURIComponent(operationId)}/retry`, {})
      const message = data.success
        ? `Retry completed via ${data.provider} (${data.model})`
        : `Retry failed via ${data.provider} (${data.model})`
      toast?.(message, Boolean(data.success))
      await load()
    } catch (e) {
      toast?.(formatErrorWithRef(e), false)
    } finally {
      setRetryingOperationId('')
    }
  }

  // Reset to the first page whenever a filter narrows the result set.
  function changeFilter(setter, value) {
    setOffset(0)
    setter(value)
  }

  return (
    <div className="admin-card">
      <div className="admin-card-title">
        Recent operations
        <HelpTip text="Metadata always; failure bodies only when AI_OPERATIONS_STORE_FAILURE_PAYLOADS is on." />
      </div>
      <div className="admin-filter-bar admin-filter-bar--fields" style={{ marginBottom: '0.75rem' }}>
        <label className="admin-field">
          <span className="admin-field-label">Task</span>
          <Select
            className="admin-select"
            value={taskFilter}
            onChange={(v) => changeFilter(setTaskFilter, v)}
            options={[
              { value: '', label: 'All' },
              ...Object.entries(TASK_LABELS).map(([id, label]) => ({ value: id, label })),
            ]}
          />
        </label>
        <label className="admin-field">
          <span className="admin-field-label">Provider</span>
          <Select
            className="admin-select"
            value={providerFilter}
            onChange={(v) => changeFilter(setProviderFilter, v)}
            options={[
              { value: '', label: 'All' },
              ...(providerOptions || []).map(p => ({ value: p, label: p })),
            ]}
          />
        </label>
        {(taskFilter || providerFilter) && (
          <button
            type="button"
            className="admin-btn admin-btn-ghost"
            onClick={() => { setOffset(0); setTaskFilter(''); setProviderFilter('') }}
          >
            Clear
          </button>
        )}
      </div>
      <AsyncSection
        data={rows}
        error={error}
        loading={loading}
        onRetry={load}
        emptyMessage={taskFilter || providerFilter ? 'No operations match these filters' : 'No AI operations recorded yet'}
      >
        {() => (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Task</th>
                    <th>Provider</th>
                    <th>Model</th>
                    <th>Result</th>
                    <th>Latency</th>
                    <th>Tokens</th>
                    <th>Context</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(row => (
                    <tr key={row.operation_id}>
                      <td className="admin-cell-nowrap">{fmtIso(row.started_at)}</td>
                      <td>{TASK_LABELS[row.task_class] || row.task_class}</td>
                      <td>{row.provider}</td>
                      <td className="admin-cell-mono">{row.model}</td>
                      <td>{resultCell(row)}</td>
                      <td>{row.latency_ms != null ? `${row.latency_ms}ms` : '—'}</td>
                      <td className="admin-cell-nowrap">
                        {row.total_tokens != null
                          ? row.total_tokens.toLocaleString()
                          : <span className="admin-text-dim">—</span>}
                      </td>
                      <td className="admin-cell-mono admin-text-dim">
                        {row.context_id || '—'}
                      </td>
                      <td className="admin-cell-nowrap">
                        {activityRowHasPayload(row) ? (
                          <div style={{ display: 'inline-flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                            <button
                              type="button"
                              className="admin-btn admin-btn-ghost"
                              onClick={() => openPayloadFor(row.operation_id)}
                            >
                              View payload
                            </button>
                            <button
                              type="button"
                              className="admin-btn admin-btn-ghost"
                              disabled={retryingOperationId === row.operation_id}
                              onClick={() => openRetryDialog(row)}
                            >
                              {retryingOperationId === row.operation_id ? 'Retrying…' : 'Retry'}
                            </button>
                          </div>
                        ) : (
                          <span className="admin-text-dim">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', alignItems: 'center' }}>
              <button className="admin-btn admin-btn-ghost" disabled={offset === 0} onClick={() => setOffset(o => Math.max(0, o - limit))}>
                Previous
              </button>
              <button className="admin-btn admin-btn-ghost" disabled={offset + limit >= total} onClick={() => setOffset(o => o + limit)}>
                Next
              </button>
              <span style={{ fontSize: '0.75rem', color: 'var(--text3)' }}>
                {offset + 1}–{Math.min(offset + limit, total)} of {total}
              </span>
            </div>
            <Modal
              open={payloadOpen}
              onClose={closePayload}
              title={payloadData ? `Payload: ${payloadData.operation_id}` : 'Payload'}
              size="lg"
              footer={(
                <Button variant="ghost" onClick={closePayload}>
                  Close
                </Button>
              )}
            >
              {payloadLoading && (
                <p className="admin-text-dim">Loading payload…</p>
              )}
              {!payloadLoading && payloadError && (
                <p className="admin-text-dim">{formatErrorWithRef(payloadError)}</p>
              )}
              {!payloadLoading && !payloadError && payloadData && (
                <div style={{ display: 'grid', gap: 'var(--space-3)' }}>
                  <p className="admin-text-dim admin-cell-mono" style={{ margin: 0 }}>
                    Task: {TASK_LABELS[payloadData.task_class] || payloadData.task_class}
                    {' · '}
                    Provider: {payloadData.provider}
                    {' · '}
                    Model: {payloadData.model}
                    {' · '}
                    Captured: {fmtIso(payloadData.created_at)}
                  </p>
                  <div>
                    <p className="admin-text-dim admin-cell-mono" style={{ margin: '0 0 var(--space-2)' }}>Messages JSON</p>
                    <pre style={PAYLOAD_PRE_STYLE}>
                      {JSON.stringify(payloadData.messages || [], null, 2)}
                    </pre>
                  </div>
                  <div>
                    <p className="admin-text-dim admin-cell-mono" style={{ margin: '0 0 var(--space-2)' }}>Response excerpt</p>
                    <pre style={PAYLOAD_PRE_STYLE}>
                      {payloadData.response_excerpt || '(none captured)'}
                    </pre>
                  </div>
                </div>
              )}
            </Modal>
            <AlertDialog
              open={Boolean(retryTarget)}
              onOpenChange={(next) => { if (!next) setRetryTarget(null) }}
              title="Retry this operation?"
              description={
                retryTarget
                  ? `Replays stored payload for ${TASK_LABELS[retryTarget.taskClass] || retryTarget.taskClass}.`
                  : ''
              }
              cancelLabel="Cancel"
              confirmLabel="Retry now"
              onConfirm={confirmRetryOperation}
            />
          </>
        )}
      </AsyncSection>
    </div>
  )
}

export default function AiOperationsPage({ toast, setPage }) {
  const [tab, setTab] = useState('overview')
  const [overview, setOverview] = useState(null)
  const [providers, setProviders] = useState(null)
  const [models, setModels] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [retrievalHealth, setRetrievalHealth] = useState(null)
  const [retrievalLoading, setRetrievalLoading] = useState(true)
  const [retrievalError, setRetrievalError] = useState(null)

  const loadRetrieval = useCallback(async () => {
    setRetrievalLoading(true)
    try {
      const res = await adminApi.getJson('/retrieval/health')
      setRetrievalHealth(res.data)
      setRetrievalError(null)
    } catch (e) {
      setRetrievalError(e)
      setRetrievalHealth(null)
    } finally {
      setRetrievalLoading(false)
    }
  }, [])

  const loadCore = useCallback(async () => {
    setLoading(true)
    try {
      const [ov, prov, mod] = await Promise.all([
        adminApi.getJson('/ai/operations/overview'),
        adminApi.getJson('/ai/operations/providers'),
        adminApi.getJson('/ai/operations/models'),
      ])
      setOverview(ov.data)
      setProviders(prov.data)
      setModels(mod.data)
      setLoadError(null)
    } catch (e) {
      setLoadError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadCore() }, [loadCore])
  useEffect(() => { loadRetrieval() }, [loadRetrieval])

  return (
    <div>
      <h1 className="admin-page-title">AI operations</h1>
      <p className="admin-page-subtitle">
        LLM provider health, retrieval index, model failover chains, and redacted usage — read-only.
        {' '}
        <Link to="/admin?p=apikeys" style={{ color: 'var(--accent)' }}>API keys &amp; config</Link>
      </p>

      <div className="admin-filter-bar" style={{ marginBottom: '1rem' }}>
        {TABS.map(t => (
          <button
            key={t.id}
            type="button"
            className={`admin-btn ${tab === t.id ? '' : 'admin-btn-ghost'}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab !== 'activity' && (
        <AsyncSection
          data={overview}
          error={loadError}
          loading={loading}
          onRetry={loadCore}
        >
          {(list) => (
            <>
              {tab === 'overview' && (
                <OverviewTab
                  overview={overview}
                  setPage={setPage}
                  retrievalHealth={retrievalHealth}
                  retrievalLoading={retrievalLoading}
                  retrievalError={retrievalError}
                  onRetryRetrieval={loadRetrieval}
                />
              )}
              {tab === 'providers' && <ProvidersTab providers={providers} />}
              {tab === 'models' && <ModelsTab models={models} />}
              {tab === 'usage' && <UsageTab overview={overview} />}
            </>
          )}
        </AsyncSection>
      )}

      {tab === 'activity' && <ActivityTab toast={toast} providerOptions={models?.providers || []} />}
    </div>
  )
}
