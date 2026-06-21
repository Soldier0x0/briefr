import { useState, useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'
import { adminApi, setAdminKey } from '../../api.js'
import StatCard from './shared/StatCard.jsx'

export default function SecurityPage({ toast }) {
  const [security, setSecurity] = useState(null)
  const [rotateOpen, setRotateOpen] = useState(false)
  const [rotateValue, setRotateValue] = useState('')

  useEffect(() => {
    adminApi.get('/security').then(r => r.json()).then(setSecurity).catch(() => {})
  }, [])

  function generateKey() {
    const arr = new Uint8Array(24)
    crypto.getRandomValues(arr)
    return btoa(String.fromCharCode(...arr)).replace(/[+/=]/g, c => ({ '+': '-', '/': '_', '=': '' }[c]))
  }

  async function saveRotatedKey() {
    if (!rotateValue.trim()) return
    try {
      const res = await adminApi.post('/config/apply-all', [{ key: 'BRIEFR_ADMIN_API_KEY', value: rotateValue }])
      const data = await res.json()
      if (res.ok) {
        setAdminKey(rotateValue)
        toast('Admin key rotated. Backend restarting…', true)
        setRotateOpen(false)
      } else {
        toast(data.detail || 'Failed to rotate key', false)
      }
    } catch (e) { toast(String(e.message), false) }
  }

  return (
    <div>
      <h1 className="admin-page-title">Security</h1>
      <p className="admin-page-subtitle">Admin-key status and recent failed authentication attempts.</p>

      {security && !security.admin_key_set && (
        <div className="admin-callout admin-callout-amber">
          <AlertTriangle size={16} strokeWidth={2} />
          <span>Admin API key not configured — routes are unauthenticated.</span>
        </div>
      )}

      {security && (
        <>
          <div className="stat-card-row">
            <StatCard label="RATE LIMIT" value={security.rate_limit_enabled ? 'ON' : 'OFF'} colorClass={security.rate_limit_enabled ? 'color-green' : 'color-amber'} />
            <StatCard label="IOC LIMIT / MIN" value={security.rate_limit_ioc_per_minute} />
            <StatCard label="REFRESH LIMIT / MIN" value={security.rate_limit_refresh_per_minute} />
            <StatCard label="ADMIN KEY" value={security.admin_key_set ? 'SET' : 'NOT SET'} colorClass={security.admin_key_set ? 'color-green' : 'color-red'} />
            <StatCard label="AUTH FAILURES (24H)" value={security.failed_auth_last_24h} colorClass={security.failed_auth_last_24h > 0 ? 'color-red' : 'color-green'} />
          </div>

          <div className="admin-card">
            <div className="admin-card-title">Admin key</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span className={`badge ${security.admin_key_set ? 'badge-ok' : 'badge-error'}`}>
                {security.admin_key_set ? 'SET' : 'NOT SET'}
              </span>
              <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.8125rem' }} onClick={() => { setRotateOpen(v => !v); setRotateValue(generateKey()) }}>
                Rotate key
              </button>
            </div>
            {rotateOpen && (
              <div style={{ marginTop: '0.75rem' }}>
                <div style={{ fontSize: '0.8125rem', color: 'var(--text3)', marginBottom: '0.4rem' }}>
                  New key (edit or use generated):
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <input className="admin-input" style={{ minWidth: 300, fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}
                    value={rotateValue} onChange={e => setRotateValue(e.target.value)} />
                  <button className="admin-btn admin-btn-primary" style={{ fontSize: '0.8rem' }} onClick={saveRotatedKey}>
                    Save & restart
                  </button>
                  <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.8rem' }} onClick={() => setRotateOpen(false)}>
                    Cancel
                  </button>
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text3)', marginTop: '0.4rem' }}>
                  Backend will restart immediately after saving. You will be logged out.
                </div>
              </div>
            )}
          </div>

          <div className="admin-card">
            <div className="admin-card-title">Auth failures (last 24h)</div>
            <div className="admin-callout admin-callout-amber" style={{ fontSize: '0.8rem' }}>
              <AlertTriangle size={16} strokeWidth={2} />
              <span>No app login yet. Auth failure tracking will appear here in V1.4 / T3-S0.</span>
            </div>
            {security.failed_auth_last_24h > 0 ? (
              <div style={{ marginTop: '0.5rem', fontSize: '0.8125rem', color: 'var(--red)' }}>
                {security.failed_auth_last_24h} auth failure(s) in last 24h
              </div>
            ) : (
              <div style={{ marginTop: '0.5rem', fontSize: '0.8125rem', color: 'var(--green)' }}>
                No auth failures in last 24h
              </div>
            )}
          </div>

          <div className="admin-card">
            <div className="admin-card-title">Top rate-limit consumers</div>
            <table className="admin-table">
              <thead><tr><th>CLIENT KEY</th><th>HITS</th></tr></thead>
              <tbody>
                {security.top_rate_limit_consumers?.length === 0 && (
                  <tr><td colSpan={2} className="admin-empty">None recorded yet</td></tr>
                )}
                {security.top_rate_limit_consumers?.map((c, i) => (
                  <tr key={i}><td className="mono" style={{ fontSize: '0.75rem' }}>{c.key}</td><td>{c.hits}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
