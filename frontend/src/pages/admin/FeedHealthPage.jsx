import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, AlertTriangle, XCircle, RefreshCw } from 'lucide-react'
import { adminApi } from '../../api.js'
import { fmtIso, sourceLabel, fmtAge } from './formatters.js'
import { nvdCadenceLabel, nvdStaleDetail, SIGMAHQ_STALE_SECONDS } from './intelStatus.js'
import HelpTip from './shared/HelpTip.jsx'
import AdminDataGrid from './shared/AdminDataGrid.jsx'
import { useOperations } from './shared/OperationTracker.jsx'
import { CIRCUIT_UI } from './circuitLabels.js'

function FeedSourceCard({
  entryKey,
  s,
  isAnalyst,
  highlighted,
  resetting,
  onReset,
}) {
  const hasError = Boolean(s.last_error)
  const lastErrorText = String(s.last_error || '').trim().toLowerCase()
  const showAiOpsEmptyHint = !isAnalyst && lastErrorText === 'empty llm response content'
  const isDegraded = !s.circuit_open && (s.consecutive_failures || 0) > 0
  let borderColor = 'var(--border)'
  let StatusIcon = CheckCircle2
  if (s.circuit_open) { borderColor = 'var(--red)'; StatusIcon = XCircle }
  else if (isDegraded || hasError) { borderColor = 'var(--amber)'; StatusIcon = AlertTriangle }
  const canReset = Boolean(s.circuit_open || isDegraded || hasError)
  const statusLabel = s.circuit_open
    ? (isAnalyst ? 'PAUSED' : CIRCUIT_UI.feedTrippedOperator)
    : (hasError || isDegraded)
      ? (isAnalyst ? 'Needs attention' : 'DEGRADED')
      : (isAnalyst ? 'Healthy' : 'OK')
  const badgeClass = s.circuit_open
    ? 'badge-error'
    : (hasError || isDegraded)
      ? 'badge-warn'
      : 'badge-ok'
  return (
    <div
      className={`feed-source-card${highlighted ? ' feed-source-card--highlight' : ''}`}
      style={{ borderLeftColor: borderColor }}
    >
      <div className="feed-source-name">{sourceLabel(entryKey)}</div>
      <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', margin: '0.4rem 0' }}>
        <span className={`badge ${badgeClass}`}>
          <StatusIcon size={11} strokeWidth={2.25} style={{ marginRight: '0.25rem', verticalAlign: '-1px' }} />
          {statusLabel}
        </span>
        {!isAnalyst && s.consecutive_failures > 0 && (
          <span className="badge badge-warn">{s.consecutive_failures} fail{s.consecutive_failures !== 1 ? 's' : ''}</span>
        )}
      </div>
      {!isAnalyst && (
        <div style={{ fontSize: '0.7rem', color: 'var(--text3)' }}>
          {s.last_success ? `✓ ${fmtIso(s.last_success)}` : 'Never succeeded'}
        </div>
      )}
      {!isAnalyst && s.last_error && (
        <div style={{ fontSize: '0.7rem', color: 'var(--amber)', marginTop: '0.2rem', wordBreak: 'break-all' }} title={s.last_error}>
          {s.last_error.slice(0, 120)}
        </div>
      )}
      {showAiOpsEmptyHint && (
        <div style={{ fontSize: 'var(--type-meta, 0.75rem)', marginTop: 'var(--space-2)' }}>
          <Link to="/admin?p=aiops" style={{ color: 'var(--accent)' }}>
            See Admin → AI operations (error: empty)
          </Link>
        </div>
      )}
      <button
        className="admin-btn admin-btn-danger"
        style={{ marginTop: '0.5rem', fontSize: '0.7rem', padding: '0.15rem 0.5rem' }}
        disabled={!canReset || resetting}
        onClick={() => onReset(entryKey)}
        title={
          canReset
            ? (isAnalyst ? 'Clear the error state and try fetching again' : CIRCUIT_UI.resetPauseTitle)
            : 'No errors to clear — source is healthy'
        }
      >
        {resetting
          ? <><span className="admin-spinner" /> {isAnalyst ? 'Retrying…' : CIRCUIT_UI.resetPauseProgress}</>
          : (isAnalyst ? 'Try again' : CIRCUIT_UI.resetPause)}
      </button>
    </div>
  )
}

export default function FeedHealthPage({ system, toast, mode = 'operator', onReload, highlightSource = '' }) {
  const { runAction } = useOperations()
  const isAnalyst = mode === 'analyst'
  const [refreshing, setRefreshing] = useState({})
  const [rebuilding, setRebuilding] = useState(false)
  const [resetting, setResetting] = useState({})
  const [sigmahqBusy, setSigmahqBusy] = useState(false)
  const sources = system?.feeds?.sources || {}
  const incidents = system?.feeds?.incidents
  const sigmahq = system?.feeds?.sigmahq_index
  const incidentSources = incidents?.sources || []
  const nvdAge = system?.last_nvd_sync_age_seconds
  const nvdSyncStale = nvdAge != null && nvdAge > 7200
  const sigmahqStale = sigmahq?.age_seconds != null && sigmahq.age_seconds > SIGMAHQ_STALE_SECONDS
  const sigmahqEmpty = !sigmahq?.rules_active

  async function runSigmahqSync({ force = false } = {}) {
    setSigmahqBusy(true)
    try {
      await runAction({
        id: force ? 'sigmahq-force' : 'sigmahq-sync',
        label: force ? 'Force re-syncing SigmaHQ index' : 'Syncing SigmaHQ index',
        kind: 'feed',
        successMessage: force
          ? 'SigmaHQ force re-sync started'
          : 'SigmaHQ index sync started',
        execute: async () => {
          if (force) {
            const { data, requestId } = await adminApi.postJson('/feeds/sigmahq/force-resync', {})
            if (data?.ok === false) {
              const err = new Error(data.detail || 'Force re-sync failed')
              err.requestId = requestId
              throw err
            }
            return { requestId }
          }
          const { data, requestId } = await adminApi.postJson('/scheduler/run', {
            job_id: 'sigmahq_index_sync',
          })
          if (!data.ok) {
            const err = new Error(data.detail || 'Failed')
            err.requestId = requestId
            throw err
          }
          return { requestId }
        },
      })
      onReload?.()
    } catch {
      // toast handled by runAction
    } finally {
      setSigmahqBusy(false)
    }
  }

  async function resetCircuit(sourceId) {
    setResetting(prev => ({ ...prev, [sourceId]: true }))
    try {
      await runAction({
        id: `circuit-${sourceId}`,
        label: `Resetting ${sourceLabel(sourceId)}`,
        kind: 'circuit',
        meta: { sourceId },
        successMessage: isAnalyst ? 'Trying again' : `Resumed retries for ${sourceLabel(sourceId)}`,
        execute: async () => {
          const { requestId } = await adminApi.postJson(
            `/feeds/${encodeURIComponent(sourceId)}/reset-circuit`,
            {},
          )
          return { requestId }
        },
      })
      onReload?.()
    } catch {
      // toast handled by runAction
    } finally {
      setResetting(prev => ({ ...prev, [sourceId]: false }))
    }
  }

  async function rebuildFeed() {
    setRebuilding(true)
    try {
      await runAction({
        id: 'incident-rebuild',
        label: 'Rebuilding incidents feed',
        kind: 'incident',
        successMessage: 'Incident feed rebuild started',
        execute: async () => {
          const { data, requestId } = await adminApi.postJson('/scheduler/run', { job_id: 'incident_feed_refresh' })
          if (!data.ok) {
            const err = new Error(data.detail || 'Failed')
            err.requestId = requestId
            throw err
          }
          return { requestId, data }
        },
      })
      setTimeout(() => onReload?.(), 1500)
    } catch {
      // toast handled by runAction
    } finally {
      setRebuilding(false)
    }
  }

  async function refreshSource(sourceId) {
    setRefreshing(prev => ({ ...prev, [sourceId]: true }))
    try {
      await runAction({
        id: `incident-${sourceId}`,
        label: `Refreshing ${sourceId}`,
        kind: 'incident',
        meta: { sourceId },
        successMessage: `Refreshing ${sourceId}`,
        execute: async () => {
          const { data, requestId } = await adminApi.postJson('/incidents/refresh', { sources: [sourceId] })
          if (!data.ok) {
            const err = new Error(data.detail || 'Failed')
            err.requestId = requestId
            throw err
          }
          return { requestId, data }
        },
      })
      setTimeout(() => onReload?.(), 1500)
    } catch {
      // toast handled by runAction
    } finally {
      setTimeout(() => setRefreshing(prev => ({ ...prev, [sourceId]: false })), 500)
    }
  }

  const entries = Object.entries(sources)
  const openCircuits = entries.filter(([, s]) => s.circuit_open)
  const degraded = entries.filter(([, s]) => !s.circuit_open && ((s.consecutive_failures || 0) > 0 || s.last_error))
  const healthy = entries.filter(([, s]) => !s.circuit_open && !(s.consecutive_failures > 0) && !s.last_error)

  function sortByFailures(list) {
    return [...list].sort(([, a], [, b]) => (b.consecutive_failures || 0) - (a.consecutive_failures || 0))
  }

  return (
    <div>
      <h1 className="admin-page-title">{isAnalyst ? 'Source status' : 'Feed health'}</h1>
      <p className="admin-page-subtitle">
        {isAnalyst
          ? 'Which intel sources are current and which need attention.'
          : 'Per-source API reachability and failure counts. OK means the last HTTP check succeeded — scheduled sync freshness is tracked separately below.'}
      </p>

      {nvdSyncStale && (
        <div className="admin-callout admin-callout-amber" role="alert" style={{ marginBottom: '1rem' }}>
          <strong>Scheduled NVD sync is overdue.</strong>{' '}
          {nvdStaleDetail(system) || `Last successful ingest was ${fmtAge(nvdAge)} ago.`}{' '}
          Expected cadence: {nvdCadenceLabel(system)}.
          {' '}The NVD API row may still show OK if a recent health check passed — run{' '}
          <strong>NVD Incremental Sync</strong> from Scheduler to refresh CVE data.
        </div>
      )}

      {entries.length === 0 ? (
        <div className="admin-empty">No health data yet — sources initialize on first fetch.</div>
      ) : (
        <>
          {openCircuits.length > 0 && (
            <div style={{ marginBottom: '1.25rem' }}>
              <div className="admin-card-title" style={{ color: 'var(--red)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                {isAnalyst ? `Sources temporarily paused (${openCircuits.length})` : `Sources paused (${openCircuits.length})`}
                {!isAnalyst && <HelpTip text="After repeated fetch failures BRIEFR pauses calls to that source so it does not keep hammering an unresponsive upstream. Retries resume automatically after a cooldown, or you can force-resume below. LLM rows (groq/gemini/cerebras/…) reflect real chat traffic — ConnectError / name-resolution usually means host DNS or egress cannot reach that provider. Empty LLM response content means HTTP succeeded but the model returned a blank body." />}
              </div>
              <div className="feed-card-grid">
                {sortByFailures(openCircuits).map(([key, s]) => (
                  <FeedSourceCard
                    key={key}
                    entryKey={key}
                    s={s}
                    isAnalyst={isAnalyst}
                    highlighted={highlightSource === key}
                    resetting={Boolean(resetting[key])}
                    onReset={resetCircuit}
                  />
                ))}
              </div>
            </div>
          )}
          {degraded.length > 0 && (
            <div style={{ marginBottom: '1.25rem' }}>
              <div className="admin-card-title" style={{ color: 'var(--amber)' }}>Degraded — recent failures ({degraded.length})</div>
              <div className="feed-card-grid">
                {sortByFailures(degraded).map(([key, s]) => (
                  <FeedSourceCard
                    key={key}
                    entryKey={key}
                    s={s}
                    isAnalyst={isAnalyst}
                    highlighted={highlightSource === key}
                    resetting={Boolean(resetting[key])}
                    onReset={resetCircuit}
                  />
                ))}
              </div>
            </div>
          )}
          {healthy.length > 0 && (
            <div className="feed-health-table-wrap" style={{ marginBottom: '1.25rem' }}>
              <div className="admin-card-title" style={{ color: 'var(--green)' }}>Healthy ({healthy.length})</div>
              <AdminDataGrid
                gridId="feed-health-healthy"
                emptyMessage="No healthy sources"
                columns={[
                  { id: 'source', label: 'Source', defaultVisible: true, minWidth: 140, render: (r) => sourceLabel(r.id) },
                  { id: 'status', label: 'Status', defaultVisible: true, width: 100, render: () => (
                    <span className="badge badge-ok">OK</span>
                  ) },
                  { id: 'last_success', label: 'Last heartbeat', defaultVisible: true, minWidth: 160, render: (r) => (
                    <span style={{ fontSize: '0.75rem', color: 'var(--text3)' }}>
                      {r.last_success ? fmtIso(r.last_success) : 'Never succeeded'}
                    </span>
                  ) },
                ]}
                rows={healthy.map(([key, s]) => ({ id: key, last_success: s.last_success }))}
                rowKey={(r) => r.id}
              />
            </div>
          )}
        </>
      )}

      {sigmahq && (
        <div className="admin-card" style={{ marginTop: '1rem' }}>
          <div className="admin-card-title">SigmaHQ detection index</div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text3)', margin: '0 0 0.6rem' }}>
            Local mirror of SigmaHQ rules (DRL-1.1). Detect serves CVE-exact matches from this index — not live GitHub search when populated.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <span className={`badge ${sigmahqEmpty || sigmahqStale ? 'badge-warn' : 'badge-ok'}`}>
              {sigmahqEmpty ? 'EMPTY' : sigmahqStale ? 'STALE' : 'INDEXED'}
            </span>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text2)' }}>
              {sigmahq.rules_active ?? 0} active · {sigmahq.cve_links ?? 0} CVE links
              {sigmahq.commit_sha ? ` · ${(sigmahq.commit_sha || '').slice(0, 12)}` : ''}
              {sigmahq.archive_sha256 ? ` · sha ${(sigmahq.archive_sha256 || '').slice(0, 8)}` : ''}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text3)' }}>
              {sigmahq.synced_at
                ? `Synced ${fmtIso(sigmahq.synced_at)}${sigmahq.age_seconds != null ? ` (${fmtAge(sigmahq.age_seconds)})` : ''}`
                : 'Never synced'}
            </div>
            {!isAnalyst && (
              <>
                <button
                  className="admin-btn admin-btn-ghost"
                  style={{ fontSize: '0.75rem' }}
                  onClick={() => runSigmahqSync({ force: false })}
                  disabled={sigmahqBusy || sigmahq.enabled === false}
                  title="Run sigmahq_index_sync (respects watermark)"
                >
                  {sigmahqBusy
                    ? <><span className="admin-spinner" /> Working…</>
                    : <><RefreshCw size={13} strokeWidth={2} /> Sync SigmaHQ index</>}
                </button>
                <button
                  className="admin-btn admin-btn-ghost"
                  style={{ fontSize: '0.75rem' }}
                  onClick={() => runSigmahqSync({ force: true })}
                  disabled={sigmahqBusy || sigmahq.enabled === false}
                  title="Clears archive identity and re-applies the index"
                >
                  Force re-sync
                </button>
                <HelpTip text="Run sync respects the commit/sha watermark. Force re-sync clears the watermark and re-downloads/applies (unlike EPSS force, which only clears)." />
              </>
            )}
          </div>
        </div>
      )}

      {incidents && (
        <div className="admin-card" style={{ marginTop: '1rem' }}>
          <div className="admin-card-title">Incidents snapshot</div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text3)', margin: '0 0 0.6rem' }}>
            The "Recent incidents" feed shown on the dashboard — built from security news RSS, separate from CVE/KEV/EPSS data.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <div>
              <span className={`badge ${incidents.stale ? 'badge-warn' : 'badge-ok'}`}>
                {incidents.stale ? 'STALE' : 'FRESH'}
              </span>
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text2)' }}>
              Last built: {fmtIso(incidents.last_refresh)}
            </div>
            <button
              className="admin-btn admin-btn-ghost"
              style={{ fontSize: '0.75rem' }}
              onClick={rebuildFeed}
              disabled={rebuilding}
              title="Rebuilds the incident/news feed snapshot — does not affect CVE, KEV, or EPSS data"
            >
              {rebuilding
                ? <><span className="admin-spinner" /> Rebuilding…</>
                : <><RefreshCw size={13} strokeWidth={2} /> Rebuild incidents feed</>}
            </button>
            <HelpTip text="Rebuilds the incident/news feed snapshot shown on the dashboard. Does not affect CVE, KEV, or EPSS data." />
          </div>

          {incidentSources.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <div className="admin-card-title" style={{ fontSize: '0.75rem', marginBottom: '0.5rem' }}>
                {isAnalyst ? 'Refresh by source' : 'Per-source refresh'}
              </div>
              <p style={{ fontSize: '0.7rem', color: 'var(--text3)', margin: '0 0 0.6rem' }}>
                {isAnalyst
                  ? 'Refresh one news outlet or ATLAS without rebuilding everything. ATLAS reloads from local data — run the MITRE/ATLAS job first for upstream updates.'
                  : 'Refresh a single RSS outlet or ATLAS slice. ATLAS reloads from the local DB; run Weekly MITRE ATT&CK + ATLAS Refresh for upstream YAML.'}
              </p>
              <div className="feed-card-grid">
                {incidentSources.map(src => {
                  const highlighted = highlightSource && src.id === highlightSource
                  return (
                  <div
                    key={src.id}
                    className={`feed-source-card${highlighted ? ' feed-source-card--highlight' : ''}`}
                    style={{ borderLeftColor: src.stale ? 'var(--amber)' : 'var(--green)' }}
                  >
                    <div className="feed-source-name">{src.label}</div>
                    <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', margin: '0.35rem 0' }}>
                      <span className={`badge ${src.stale ? 'badge-warn' : 'badge-ok'}`}>
                        {src.kind === 'atlas' ? 'ATLAS' : 'RSS'}
                      </span>
                      {!isAnalyst && (
                        <span style={{ fontSize: '0.7rem', color: 'var(--text3)' }}>
                          {src.snapshot_item_count ?? src.item_count ?? 0} in feed
                        </span>
                      )}
                    </div>
                    {!isAnalyst && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--text3)' }}>
                        {src.cached_at ? `Cached: ${fmtIso(src.cached_at)}` : 'No cache yet'}
                      </div>
                    )}
                    {!isAnalyst && src.last_error && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--amber)', marginTop: '0.2rem', wordBreak: 'break-all' }}>
                        {src.last_error.slice(0, 80)}
                      </div>
                    )}
                    <button
                      className="admin-btn admin-btn-ghost"
                      style={{ marginTop: '0.5rem', fontSize: '0.7rem', padding: '0.15rem 0.5rem' }}
                      disabled={!!refreshing[src.id]}
                      onClick={() => refreshSource(src.id)}
                    >
                      <RefreshCw size={12} strokeWidth={2} /> {refreshing[src.id] ? 'Refreshing…' : 'Refresh'}
                    </button>
                  </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
