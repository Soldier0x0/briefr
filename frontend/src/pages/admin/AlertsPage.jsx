import { useState, useEffect } from 'react'
import { adminApi } from '../../api.js'

export default function AlertsPage({ toast }) {
  const [config, setConfig] = useState(null)
  const [results, setResults] = useState({})
  const [testing, setTesting] = useState({})

  useEffect(() => {
    adminApi.get('/config').then(r => r.json()).then(setConfig).catch(() => {})
  }, [])

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

  return (
    <div>
      <h1 className="admin-page-title">Alert channels</h1>
      <p className="admin-page-subtitle">Where BRIEFR sends alerts. To change URLs or tokens, switch to Operator view → Webhooks / API keys.</p>

      <div className="admin-card">
        {['discord', 'telegram'].map(ch => (
          <div key={ch} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.5rem 0' }}>
            <span className={`pill ${channelConfigured(ch) ? 'pill-green' : 'pill-gray'}`} style={{ textTransform: 'capitalize' }}>
              {ch}
            </span>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text2)' }}>
              {channelConfigured(ch) ? 'Configured' : 'Not configured'}
            </span>
            {results[ch] && (
              <span className={`badge ${results[ch].ok ? 'badge-ok' : 'badge-error'}`}>
                {results[ch].ok ? 'delivered' : 'failed'}
              </span>
            )}
            <button
              className="admin-btn admin-btn-ghost"
              style={{ fontSize: '0.75rem', marginLeft: 'auto' }}
              onClick={() => channelConfigured(ch) && testWebhook(ch)}
              disabled={testing[ch] || !channelConfigured(ch)}
            >
              {testing[ch] ? 'Testing…' : `Test ${ch}`}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
