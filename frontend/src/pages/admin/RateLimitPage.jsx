import { useState, useEffect } from 'react'
import { adminApi } from '../../api.js'

function BucketRow({ bucket, expanded, onToggle }) {
  return (
    <>
      <tr>
        <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{bucket.name}</td>
        <td>{bucket.rate_per_minute}/min</td>
        <td>{bucket.total_hits.toLocaleString()}</td>
        <td>{bucket.active_keys}</td>
        <td>
          {bucket.top_consumers.length > 0 && (
            <button className="admin-btn admin-btn-sm" onClick={onToggle}>
              {expanded ? 'Hide' : `Show ${bucket.top_consumers.length}`}
            </button>
          )}
        </td>
      </tr>
      {expanded && bucket.top_consumers.map(c => (
        <tr key={c.key} style={{ background: 'var(--bg3)' }}>
          <td colSpan={3} style={{ paddingLeft: '2rem', fontFamily: 'monospace', fontSize: '0.78rem', color: 'var(--fg2)' }}>
            {c.key}
          </td>
          <td colSpan={2} style={{ fontSize: '0.78rem', color: 'var(--fg2)' }}>
            {c.hits.toLocaleString()} hits
          </td>
        </tr>
      ))}
    </>
  )
}

export default function RateLimitPage({ toast }) {
  const [data, setData] = useState(null)
  const [expanded, setExpanded] = useState({})

  useEffect(() => {
    adminApi.get('/ratelimit').then(r => r.json()).then(setData).catch(e => toast(e.message, false))
  }, [])

  function toggle(name) {
    setExpanded(prev => ({ ...prev, [name]: !prev[name] }))
  }

  return (
    <div>
      <h1 className="admin-page-title">Rate limit</h1>
      <p className="admin-page-subtitle">Per-bucket request counters and top consumers since last restart.</p>

      {data && (
        <div className="admin-callout" style={{ marginBottom: '1rem' }}>
          <span>
            Rate limiting is{' '}
            <strong style={{ color: data.enabled ? 'var(--green)' : 'var(--amber)' }}>
              {data.enabled ? 'enabled' : 'disabled'}
            </strong>
            . To change this, update <code>BRIEFR_RATE_LIMIT_ENABLED</code> in{' '}
            <a href="#" onClick={e => { e.preventDefault(); }} style={{ color: 'var(--fg2)' }}>API keys &amp; config</a>.
          </span>
        </div>
      )}

      <div className="admin-card">
        <div className="admin-card-title">Buckets</div>
        {!data ? (
          <p style={{ color: 'var(--fg3)', fontSize: '0.85rem', margin: '0.5rem 0 0' }}>Loading…</p>
        ) : (
          <div style={{ overflowX: 'auto', marginTop: '0.5rem' }}>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Bucket</th>
                  <th>Limit</th>
                  <th>Total hits</th>
                  <th>Active keys</th>
                  <th>Top consumers</th>
                </tr>
              </thead>
              <tbody>
                {data.buckets.map(b => (
                  <BucketRow
                    key={b.name}
                    bucket={b}
                    expanded={!!expanded[b.name]}
                    onToggle={() => toggle(b.name)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
