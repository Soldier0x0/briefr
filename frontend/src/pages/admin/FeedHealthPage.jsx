import { useState } from 'react'
import { CheckCircle2, AlertTriangle, XCircle, RefreshCw } from 'lucide-react'
import { adminApi } from '../../api.js'
import { fmtIso, sourceLabel } from './formatters.js'
import HelpTip from './shared/HelpTip.jsx'

export default function FeedHealthPage({ system, toast, mode = 'operator', onReload }) {
  const isAnalyst = mode === 'analyst'
  const [refreshing, setRefreshing] = useState({})
  const sources = system?.feeds?.sources || {}
  const incidents = system?.feeds?.incidents
  const incidentSources = incidents?.sources || []

  async function resetCircuit(sourceId) {
    try {
      await adminApi.post(`/feeds/${encodeURIComponent(sourceId)}/reset-circuit`, {})
      toast(isAnalyst ? 'Trying again' : `Circuit reset for ${sourceId}`, true)
    } catch (e) { toast(String(e.message), false) }
  }

  async function rebuildFeed() {
    try {
      const res = await adminApi.post('/scheduler/run', { job_id: 'incident_feed_refresh' })
      const data = await res.json()
      toast(data.ok ? 'Incident feed rebuild started' : data.detail || 'Failed', data.ok)
      if (data.ok) setTimeout(() => onReload?.(), 1500)
    } catch (e) { toast(String(e.message), false) }
  }

  async function refreshSource(sourceId) {
    setRefreshing(prev => ({ ...prev, [sourceId]: true }))
    try {
      const res = await adminApi.post('/incidents/refresh', { sources: [sourceId] })
      const data = await res.json()
      toast(data.ok ? `Refreshing ${sourceId}` : data.detail || 'Failed', data.ok)
      if (data.ok) setTimeout(() => onReload?.(), 1500)
    } catch (e) { toast(String(e.message), false) }
    setTimeout(() => setRefreshing(prev => ({ ...prev, [sourceId]: false })), 2000)
  }

  function FeedCard({ entryKey, s }) {
    let borderColor = 'var(--border)'
    let StatusIcon = CheckCircle2
    if (s.circuit_open) { borderColor = 'var(--red)'; StatusIcon = XCircle }
    else if (s.consecutive_failures > 0) { borderColor = 'var(--amber)'; StatusIcon = AlertTriangle }
    return (
      <div key={entryKey} className="feed-source-card" style={{ borderLeftColor: borderColor }}>
        <div className="feed-source-name">{sourceLabel(entryKey)}</div>
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', margin: '0.4rem 0' }}>
          <span className={`badge ${s.circuit_open ? 'badge-error' : 'badge-ok'}`}>
            <StatusIcon size={11} strokeWidth={2.25} style={{ marginRight: '0.25rem', verticalAlign: '-1px' }} />
            {s.circuit_open ? (isAnalyst ? 'PAUSED' : 'OPEN') : (isAnalyst ? 'Healthy' : 'CLOSED')}
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
          <div style={{ fontSize: '0.7rem', color: 'var(--amber)', marginTop: '0.2rem', wordBreak: 'break-all' }}>
            {s.last_error.slice(0, 80)}
          </div>
        )}
        <button
          className="admin-btn admin-btn-danger"
          style={{ marginTop: '0.5rem', fontSize: '0.7rem', padding: '0.15rem 0.5rem' }}
          disabled={!s.circuit_open && !(s.consecutive_failures > 0) && !s.last_error}
          onClick={() => resetCircuit(entryKey)}
          title={
            s.circuit_open
              ? 'Circuit is open — clear the pause and allow retries'
              : (s.last_error || s.consecutive_failures > 0)
                ? 'Clear failure state and allow the next scheduled fetch to retry'
                : 'No failures to reset'
          }
        >
          {isAnalyst ? 'Try again' : 'Reset circuit'}
        </button>
      </div>
    )
  }

  const entries = Object.entries(sources)
  const openCircuits = entries.filter(([, s]) => s.circuit_open)
  const degraded = entries.filter(([, s]) => !s.circuit_open && (s.consecutive_failures || 0) > 0)
  const healthy = entries.filter(([, s]) => !s.circuit_open && !(s.consecutive_failures > 0))

  function sortByFailures(list) {
    return [...list].sort(([, a], [, b]) => (b.consecutive_failures || 0) - (a.consecutive_failures || 0))
  }

  return (
    <div>
      <h1 className="admin-page-title">{isAnalyst ? 'Source status' : 'Feed health'}</h1>
      <p className="admin-page-subtitle">
        {isAnalyst
          ? 'Which intel sources are current and which need attention.'
          : 'Per-source ingest status and consecutive-failure counts for every upstream feed (NVD, KEV, EPSS, etc.).'}
      </p>

      {entries.length === 0 ? (
        <div className="admin-empty">No health data yet — sources initialize on first fetch.</div>
      ) : (
        <>
          {openCircuits.length > 0 && (
            <div style={{ marginBottom: '1.25rem' }}>
              <div className="admin-card-title" style={{ color: 'var(--red)' }}>
                {isAnalyst ? `Sources temporarily paused (${openCircuits.length})` : `Open circuits (${openCircuits.length})`}
              </div>
              <div className="feed-card-grid">
                {sortByFailures(openCircuits).map(([key, s]) => <FeedCard key={key} entryKey={key} s={s} />)}
              </div>
            </div>
          )}
          {degraded.length > 0 && (
            <div style={{ marginBottom: '1.25rem' }}>
              <div className="admin-card-title" style={{ color: 'var(--amber)' }}>Degraded — recent failures ({degraded.length})</div>
              <div className="feed-card-grid">
                {sortByFailures(degraded).map(([key, s]) => <FeedCard key={key} entryKey={key} s={s} />)}
              </div>
            </div>
          )}
          {healthy.length > 0 && (
            <div style={{ marginBottom: '1.25rem' }}>
              <div className="admin-card-title" style={{ color: 'var(--green)' }}>Healthy ({healthy.length})</div>
              <div className="feed-card-grid">
                {healthy.map(([key, s]) => <FeedCard key={key} entryKey={key} s={s} />)}
              </div>
            </div>
          )}
        </>
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
              title="Rebuilds the incident/news feed snapshot — does not affect CVE, KEV, or EPSS data"
            >
              <RefreshCw size={13} strokeWidth={2} /> Rebuild incidents feed
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
                {incidentSources.map(src => (
                  <div key={src.id} className="feed-source-card" style={{ borderLeftColor: src.stale ? 'var(--amber)' : 'var(--green)' }}>
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
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
