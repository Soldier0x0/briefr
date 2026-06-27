import { useState, useEffect } from 'react'
import { adminApi } from '../../api.js'
import StatCard from './shared/StatCard.jsx'

const RATE_LIMIT_BUCKET_LABELS = {
  ioc: 'IOC lookups',
  refresh: 'Manual refresh / ingest',
  admin_read: 'Admin read (GET)',
  wallboard: 'Wallboard API',
  login: 'Login / setup (per IP)',
  login_username: 'Login / setup (per username)',
  auth_refresh: 'Session refresh',
}

export default function SecurityPage({ toast }) {
  const [security, setSecurity] = useState(null)

  useEffect(() => {
    adminApi.get('/security').then(r => r.json()).then(setSecurity).catch(() => {})
  }, [])

  return (
    <div>
      <h1 className="admin-page-title">Security</h1>
      <p className="admin-page-subtitle">
        App login activity and in-process rate-limit usage. BRIEFR uses session cookies for admin access — no separate admin API key is required.
      </p>

      {security && (
        <>
          <div className="stat-card-row">
            <StatCard label="RATE LIMIT" value={security.rate_limit_enabled ? 'ON' : 'OFF'} colorClass={security.rate_limit_enabled ? 'color-green' : 'color-amber'} />
            <StatCard label="LOGIN LIMIT / MIN" value={security.rate_limit_login_per_minute ?? '—'} />
            <StatCard label="AUTH REFRESH / MIN" value={security.rate_limit_auth_refresh_per_minute ?? '—'} />
            <StatCard label="LOGIN FAILURES (24H)" value={security.failed_auth_last_24h} colorClass={security.failed_auth_last_24h > 0 ? 'color-red' : 'color-green'} />
          </div>
          <div className="stat-card-row">
            <StatCard label="IOC LIMIT / MIN" value={security.rate_limit_ioc_per_minute ?? '—'} />
            <StatCard label="REFRESH LIMIT / MIN" value={security.rate_limit_refresh_per_minute ?? '—'} />
            <StatCard label="ADMIN READ / MIN" value={security.rate_limit_admin_read_per_minute ?? '—'} />
          </div>

          <div className="admin-card">
            <div className="admin-card-title">Login failures (last 24h)</div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text2)', margin: '0 0 0.75rem', lineHeight: 1.5 }}>
              Failed username/password attempts against the built-in app login ({security.failed_auth_last_24h} in the last 24 hours).
            </p>
            {security.failed_auth_last_24h > 0 ? (
              <div style={{ fontSize: '0.8125rem', color: 'var(--red)' }}>
                {security.failed_auth_last_24h} failed login attempt(s) — check Audit log for details.
              </div>
            ) : (
              <div style={{ fontSize: '0.8125rem', color: 'var(--green)' }}>
                No failed logins in the last 24h
              </div>
            )}
          </div>

          <div className="admin-card">
            <div className="admin-card-title">Rate-limit usage (since backend start)</div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text2)', margin: '0 0 0.75rem', lineHeight: 1.5 }}>
              Each row is a client IP (or Cloudflare-attested IP behind the proxy), or a username for login throttling.
              <strong> Hits</strong> count requests that consumed a rate-limit token — IOC lookups, manual refresh/ingest, admin reads, and auth endpoints.
              Limits reset continuously (token bucket); high counts mean that client is busy, not that they are blocked forever.
            </p>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>CLIENT / USER</th>
                  <th>ENDPOINT GROUP</th>
                  <th>HITS</th>
                </tr>
              </thead>
              <tbody>
                {security.top_rate_limit_consumers?.length === 0 && (
                  <tr><td colSpan={3} className="admin-empty">No rate-limited requests recorded yet</td></tr>
                )}
                {security.top_rate_limit_consumers?.map((c, i) => (
                  <tr key={i}>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{c.key}</td>
                    <td>{RATE_LIMIT_BUCKET_LABELS[c.bucket] || c.bucket}</td>
                    <td>{c.hits}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
