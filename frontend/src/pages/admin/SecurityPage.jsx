import { useState, useEffect } from 'react'
import { AlertTriangle, ExternalLink } from 'lucide-react'
import { adminApi } from '../../api.js'
import HelpTip from './shared/HelpTip.jsx'
import StatCard from './shared/StatCard.jsx'

export default function SecurityPage() {
  const [security, setSecurity] = useState(null)

  useEffect(() => {
    adminApi.get('/security').then(r => r.json()).then(setSecurity).catch(() => {})
  }, [])

  const wallboardWarning = security?.posture_warnings?.find(w => w.flag?.includes('WALLBOARD'))

  return (
    <div>
      <h1 className="admin-page-title">Security</h1>
      <p className="admin-page-subtitle">Production posture, rate-limit status, wallboard access, and recent failed authentication attempts.</p>

      {security && security.posture_warnings?.length > 0 && security.posture_warnings.map(w => (
        <div className="admin-callout admin-callout-amber" key={w.flag}>
          <AlertTriangle size={16} strokeWidth={2} />
          <span><strong>{w.flag}</strong> — {w.message}</span>
        </div>
      ))}

      {security && (
        <div className="stat-card-row">
          <StatCard label="RATE LIMIT" value={security.rate_limit_enabled ? 'ON' : 'OFF'} colorClass={security.rate_limit_enabled ? 'color-green' : 'color-amber'} />
          <StatCard label="IOC LIMIT / MIN" value={security.rate_limit_ioc_per_minute} />
          <StatCard label="REFRESH LIMIT / MIN" value={security.rate_limit_refresh_per_minute} />
          <StatCard label="AUTH FAILURES (24H)" value={security.failed_auth_last_24h} colorClass={security.failed_auth_last_24h > 0 ? 'color-red' : 'color-green'} />
        </div>
      )}

      <div className="admin-card" style={{ marginTop: '1rem' }}>
        <div className="admin-card-title" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
          Wallboard kiosk
          <HelpTip text="Read-only posture view for NOC displays. Optional token gate — not required for local dev." />
        </div>
        <p style={{ fontSize: '0.8125rem', color: 'var(--text2)', lineHeight: 1.45, margin: '0 0 0.75rem' }}>
          The wallboard at <code className="mono">/wallboard</code> shows aggregated intel posture without admin secrets.
          Set <code className="mono">WALLBOARD_TOKEN</code> under API keys &amp; config to require the
          <code className="mono"> X-BRIEFR-Wallboard-Token</code> header on kiosk clients.
          When the token is unset, the endpoint stays open (read-only data only) — production should set a token.
        </p>
        {wallboardWarning && (
          <p style={{ fontSize: '0.75rem', color: 'var(--amber)', margin: '0 0 0.75rem' }}>
            Posture warning active: {wallboardWarning.message}
          </p>
        )}
        <a className="admin-btn admin-btn-ghost" href="/wallboard" target="_blank" rel="noopener noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
          Open wallboard
          <ExternalLink size={14} strokeWidth={2} aria-hidden />
        </a>
      </div>

      {security?.top_rate_limit_consumers?.length > 0 && (
        <div className="admin-card" style={{ marginTop: '1rem' }}>
          <div className="admin-card-title">Top rate-limit consumers</div>
          <table className="admin-table">
            <thead><tr><th>CLIENT</th><th>BUCKET</th><th>HITS</th></tr></thead>
            <tbody>
              {security.top_rate_limit_consumers.map((row, i) => (
                <tr key={`${row.key}-${row.bucket}-${i}`}>
                  <td className="mono" style={{ fontSize: '0.75rem' }}>{row.key || '—'}</td>
                  <td className="mono" style={{ fontSize: '0.75rem' }}>{row.bucket || '—'}</td>
                  <td>{row.hits ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
