import { useState, useEffect } from 'react'
import { adminApi } from '../../api.js'
import StatCard from './shared/StatCard.jsx'

export default function SecurityPage() {
  const [security, setSecurity] = useState(null)

  useEffect(() => {
    adminApi.get('/security').then(r => r.json()).then(setSecurity).catch(() => {})
  }, [])

  return (
    <div>
      <h1 className="admin-page-title">Security</h1>
      <p className="admin-page-subtitle">Rate-limit status and recent failed authentication attempts.</p>

      {security && (
        <div className="stat-card-row">
          <StatCard label="RATE LIMIT" value={security.rate_limit_enabled ? 'ON' : 'OFF'} colorClass={security.rate_limit_enabled ? 'color-green' : 'color-amber'} />
          <StatCard label="IOC LIMIT / MIN" value={security.rate_limit_ioc_per_minute} />
          <StatCard label="REFRESH LIMIT / MIN" value={security.rate_limit_refresh_per_minute} />
          <StatCard label="AUTH FAILURES (24H)" value={security.failed_auth_last_24h} colorClass={security.failed_auth_last_24h > 0 ? 'color-red' : 'color-green'} />
        </div>
      )}
    </div>
  )
}
