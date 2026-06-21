import { CheckCircle2, AlertTriangle, XCircle, RefreshCw } from 'lucide-react'
import { adminApi } from '../../api.js'
import { fmtIso, sourceLabel } from './formatters.js'
import HelpTip from './shared/HelpTip.jsx'

export default function FeedHealthPage({ system, toast, mode = 'operator' }) {
  const isAnalyst = mode === 'analyst'
  const sources = system?.feeds?.sources || {}
  const incidents = system?.feeds?.incidents

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
    } catch (e) { toast(String(e.message), false) }
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
          disabled={!s.circuit_open}
          onClick={() => resetCircuit(entryKey)}
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
        </div>
      )}
    </div>
  )
}
