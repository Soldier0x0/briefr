import { useState, useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'
import { adminApi } from '../../api.js'
import { fmtIso } from './formatters.js'

export default function WebhooksPage({ toast }) {
  const [config, setConfig] = useState(null)
  const [results, setResults] = useState({})
  const [testing, setTesting] = useState({})
  const [log, setLog] = useState(null)
  const [logOffset, setLogOffset] = useState(0)
  const [showAddCallout, setShowAddCallout] = useState(false)
  const logLimit = 50

  useEffect(() => {
    adminApi.get('/config').then(r => r.json()).then(setConfig).catch(() => {})
  }, [])

  async function loadLog(offset = 0) {
    try {
      const res = await adminApi.get(`/webhooks/log?limit=${logLimit}&offset=${offset}`)
      setLog(await res.json())
      setLogOffset(offset)
    } catch { }
  }

  useEffect(() => { loadLog() }, [])

  async function testWebhook(channel) {
    setTesting(t => ({ ...t, [channel]: true }))
    try {
      const res = await adminApi.post('/config/webhook-test', { channel })
      const data = await res.json()
      setResults(r => ({ ...r, [channel]: data }))
      toast(data.ok ? `${channel} delivered` : `${channel} failed: ${data.error}`, data.ok)
    } catch (e) { toast(String(e.message), false) }
    setTesting(t => ({ ...t, [channel]: false }))
  }

  function channelConfigured(ch) {
    if (ch === 'discord') return config?.webhooks?.DISCORD_WEBHOOK_URL !== 'not configured'
    if (ch === 'telegram') return config?.webhooks?.TELEGRAM_BOT_TOKEN !== 'not configured'
    return false
  }

  const stackTerms = config?.app?.BRIEFR_STACK_TERMS || ''

  return (
    <div>
      <h1 className="admin-page-title">Webhooks</h1>
      <p className="admin-page-subtitle">Test delivery and review send history for Discord/Telegram/generic alerts. Configure URLs and tokens on the API Keys page.</p>

      {config && (
        <div className="admin-card">
          <div className="admin-card-title">Configured endpoints</div>
          <table className="admin-table">
            <thead><tr><th>CHANNEL</th><th>ENDPOINT</th><th>TEST RESULT</th><th>ACTIONS</th></tr></thead>
            <tbody>
              {[['discord', config.webhooks?.DISCORD_WEBHOOK_URL], ['telegram', config.webhooks?.TELEGRAM_BOT_TOKEN]].map(([ch, val]) => (
                <tr key={ch}>
                  <td style={{ textTransform: 'capitalize', fontWeight: 600 }}>{ch}</td>
                  <td className="mono" style={{ fontSize: '0.7rem' }}>{val}</td>
                  <td>
                    {results[ch] && (
                      <span className={`badge ${results[ch].ok ? 'badge-ok' : 'badge-error'}`}>
                        {results[ch].ok ? 'delivered' : results[ch].error?.slice(0, 50)}
                      </span>
                    )}
                  </td>
                  <td>
                    <button
                      className="admin-btn admin-btn-ghost"
                      style={{ fontSize: '0.75rem', padding: '0.15rem 0.45rem', color: channelConfigured(ch) ? undefined : 'var(--text3)', cursor: channelConfigured(ch) ? 'pointer' : 'not-allowed' }}
                      onClick={() => channelConfigured(ch) && testWebhook(ch)}
                      disabled={testing[ch] || !channelConfigured(ch)}
                    >
                      {testing[ch] ? 'Testing…' : `Test ${ch}`}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: '0.75rem' }}>
            <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={() => setShowAddCallout(v => !v)}>
              Add channel
            </button>
            {showAddCallout && (
              <div className="admin-callout admin-callout-amber" style={{ marginTop: '0.5rem' }}>
                <AlertTriangle size={16} strokeWidth={2} />
                <span>Additional channels (Slack, PagerDuty) ship in V1.4.</span>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="admin-card">
        <div className="admin-card-title">Stack terms for KEV alerts</div>
        <div style={{ fontSize: '0.8125rem', color: 'var(--text2)', marginBottom: '0.5rem' }}>
          {stackTerms ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
              {stackTerms.split(',').map(t => t.trim()).filter(Boolean).map(t => (
                <span key={t} className="badge badge-muted">{t}</span>
              ))}
            </div>
          ) : <span style={{ color: 'var(--text3)' }}>No stack terms configured</span>}
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text3)' }}>
          Edit in <button className="admin-link" onClick={() => {}}>API keys &amp; config → BRIEFR_STACK_TERMS</button>
        </div>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Alert log</div>
        <div className="admin-filter-bar">
          <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={() => loadLog(0)}>Refresh</button>
        </div>
        <table className="admin-table">
          <thead><tr><th>EVENT TYPE</th><th>TARGET</th><th>ALERTED AT</th></tr></thead>
          <tbody>
            {log === null && <tr><td colSpan={3} className="admin-empty">Loading…</td></tr>}
            {log?.rows?.length === 0 && <tr><td colSpan={3} className="admin-empty">No webhook alerts logged yet</td></tr>}
            {log?.rows?.map((r, i) => (
              <tr key={i}>
                <td><span className="badge badge-muted">{r.alert_type}</span></td>
                <td className="mono" style={{ fontSize: '0.75rem' }}>{r.target}</td>
                <td style={{ fontSize: '0.75rem' }}>{fmtIso(r.alerted_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {log && (
          <div className="admin-pagination">
            <button className="admin-btn admin-btn-ghost" disabled={logOffset === 0} onClick={() => loadLog(Math.max(0, logOffset - logLimit))}>← Prev</button>
            <span style={{ color: 'var(--text3)', fontSize: '0.8125rem' }}>
              {logOffset + 1}–{Math.min(logOffset + logLimit, log.total)} of {log.total}
            </span>
            <button className="admin-btn admin-btn-ghost" disabled={logOffset + logLimit >= log.total} onClick={() => loadLog(logOffset + logLimit)}>Next →</button>
          </div>
        )}
      </div>
    </div>
  )
}
