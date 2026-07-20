import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { adminApi } from '../../api.js'
import HelpTip from './shared/HelpTip.jsx'
import { AdminTableBodySkeletonRows } from './shared/AdminSkeletons.jsx'
import { inboundBucketTip } from '../../utils/domainTermTips.js'

function BucketRow({ bucket, expanded, onToggle }) {
  const tip = inboundBucketTip(bucket.name)
  return (
    <>
      <tr>
        <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
            {bucket.name}
            {tip && <HelpTip text={tip} />}
          </span>
        </td>
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
      <h1 className="admin-page-title">
        Inbound limits
        <HelpTip text="Protects BRIEFR's own API from abuse (per-client IP buckets). Not outbound provider quota — NVD, VirusTotal, OTX limits are on IOC Lookup and AI Operations. Not LLM pacing headroom (scheduler-side)." />
      </h1>
      <p className="admin-page-subtitle">
        Per-bucket request counters and top consumers since last restart — throttling on requests <em>to</em> BRIEFR's own API.
      </p>

      {data && (
        <div className="admin-callout" style={{ marginBottom: '1rem' }}>
          <span>
            Rate limiting is{' '}
            <strong style={{ color: data.enabled ? 'var(--green)' : 'var(--amber)' }}>
              {data.enabled ? 'enabled' : 'disabled'}
            </strong>
            . To change this, update <code>RATE_LIMIT_ENABLED</code> in{' '}
            <Link to="/admin?p=apikeys" style={{ color: 'var(--accent)' }}>API keys &amp; config</Link>.
          </span>
        </div>
      )}

      <div className="admin-card">
        <div className="admin-card-title">Buckets</div>
        {!data ? (
          <table className="admin-table admin-skeleton-table" role="status" aria-label="Loading rate limit buckets">
            <tbody>
              <AdminTableBodySkeletonRows rows={5} cols={5} />
            </tbody>
          </table>
        ) : (
          <div style={{ overflowX: 'auto', marginTop: '0.5rem' }}>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Bucket</th>
                  <th>Limit</th>
                  <th>Total hits</th>
                  <th>
                    Active keys
                    <HelpTip text="Distinct client identities currently holding a rate-limit slot for this limit (usually client IPs)." />
                  </th>
                  <th>
                    Top consumers
                    <HelpTip text="Highest-hit client keys for this bucket since the last backend restart." />
                  </th>
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
