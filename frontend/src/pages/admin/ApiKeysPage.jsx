import { useState, useEffect } from 'react'
import { adminApi } from '../../api.js'
import DiffReviewModal from './shared/DiffReviewModal.jsx'

export default function ApiKeysPage({ toast }) {
  const [config, setConfig] = useState(null)
  const [queue, setQueue] = useState({}) // {key: value}
  const [editing, setEditing] = useState({}) // {key: tempValue}
  const [showDiff, setShowDiff] = useState(false)
  const [applying, setApplying] = useState(false)

  useEffect(() => {
    adminApi.get('/config').then(r => r.json()).then(setConfig).catch(() => {})
  }, [])

  function addToQueue(key, value) {
    setQueue(q => ({ ...q, [key]: value }))
    setEditing(e => { const n = { ...e }; delete n[key]; return n })
    toast(`Added ${key} to pending changes`, true)
  }

  function removeFromQueue(key) {
    setQueue(q => { const n = { ...q }; delete n[key]; return n })
  }

  async function applyAll() {
    const items = Object.entries(queue).map(([key, value]) => ({ key, value }))
    setApplying(true)
    try {
      const res = await adminApi.post('/config/apply-all', items)
      const data = await res.json()
      if (res.ok) {
        toast(`Applied ${data.changed_keys?.length} changes. Restarting…`, true)
        setQueue({})
      } else {
        const errs = data.errors || [data.detail]
        toast(`Failed: ${errs.join('; ')}`, false)
      }
    } catch (e) { toast(String(e.message), false) }
    setApplying(false)
  }

  function ConfigRow({ envKey, value, isSecret = false, writable = true, restartRequired = false }) {
    const inQueue = queue[envKey] !== undefined
    const editVal = editing[envKey]
    const isEditing = editVal !== undefined

    return (
      <div className="config-row">
        <div className="config-row-key mono">{envKey}</div>
        <div className="config-row-value">
          {inQueue ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="badge badge-warn">queued: {isSecret ? '••••' : queue[envKey]}</span>
              <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.7rem' }} onClick={() => removeFromQueue(envKey)}>×</button>
            </div>
          ) : !isEditing ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="mono" style={{ fontSize: '0.8125rem', color: 'var(--text2)' }}>{String(value)}</span>
              {restartRequired && <span className="badge badge-warn" style={{ fontSize: '0.6rem' }}>restart</span>}
              {writable && (
                <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.7rem', padding: '0.1rem 0.35rem' }}
                  onClick={() => setEditing(e => ({ ...e, [envKey]: String(value === 'not configured' ? '' : value) }))}>
                  Edit
                </button>
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <input
                className="admin-input"
                type={isSecret ? 'password' : 'text'}
                style={{ minWidth: 220 }}
                value={editVal}
                onChange={e => setEditing(ed => ({ ...ed, [envKey]: e.target.value }))}
                autoFocus
              />
              <button className="admin-btn admin-btn-primary" style={{ fontSize: '0.75rem' }}
                onClick={() => addToQueue(envKey, editVal)}>
                Add to queue
              </button>
              <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }}
                onClick={() => setEditing(e => { const n = { ...e }; delete n[envKey]; return n })}>
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  if (!config) return <div className="admin-empty">Loading…</div>

  const pendingCount = Object.keys(queue).length

  return (
    <div>
      {showDiff && pendingCount > 0 && (
        <DiffReviewModal
          changes={queue}
          applying={applying}
          onClose={() => setShowDiff(false)}
          onDiscard={() => { setQueue({}); setShowDiff(false) }}
          onApply={() => { setShowDiff(false); applyAll() }}
        />
      )}

      <h1 className="admin-page-title">API keys & config</h1>

      <div className="admin-callout admin-callout-amber">
        <code>load_dotenv()</code> is called without <code>override=True</code>. Process env vars (systemd / Cursor Secrets) win over <code>.env</code>.
        Changes here write to <code>.env</code> and take effect after restart.
      </div>

      <div className="admin-card">
        <div className="admin-card-title">API Keys</div>
        {Object.entries(config.api_keys || {}).map(([k, v]) => (
          <ConfigRow key={k} envKey={k} value={v} isSecret writable />
        ))}
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Scheduler intervals — NVD / KEV / EPSS</div>
        {['NVD_SYNC_INTERVAL_HOURS', 'KEV_SYNC_INTERVAL_MINUTES', 'EPSS_SYNC_INTERVAL_HOURS',
          'INCIDENT_FEED_REFRESH_MINUTES', 'VULNRICHMENT_SYNC_INTERVAL_HOURS', 'CVELISTV5_SYNC_INTERVAL_MINUTES'].map(k => (
          <ConfigRow key={k} envKey={k} value={config.scheduler?.[k] ?? ''} restartRequired />
        ))}
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Scheduler intervals — cron &amp; timezone</div>
        {['SCHEDULER_TIMEZONE', 'MITRE_REFRESH_HOUR', 'MITRE_REFRESH_MINUTE',
          'CORRELATION_HOUR', 'CORRELATION_MINUTE', 'CORRELATION_TIMEZONE',
          'OTX_CORRELATION_HOUR', 'OTX_CORRELATION_MINUTE', 'OTX_CORRELATION_TIMEZONE'].map(k => (
          <ConfigRow key={k} envKey={k} value={config.scheduler?.[k] ?? ''} restartRequired />
        ))}
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Ingest tuning</div>
        {['MAX_CVES_PER_FETCH', 'NVD_DAYS_BACK', 'KEV_CROSS_FETCH_NVD',
          'CVELISTV5_INITIAL_SINCE_DAYS', 'VULNRICHMENT_BRANCH', 'CVELISTV5_BRANCH'].map(k => (
          <ConfigRow key={k} envKey={k} value={config.ingest?.[k] ?? config.scheduler?.[k] ?? ''} />
        ))}
      </div>

      <div className="admin-card">
        <div className="admin-card-title">ML toggles</div>
        {Object.entries(config.ml || {}).map(([k, v]) => (
          <ConfigRow key={k} envKey={k} value={v} restartRequired={k.endsWith('_ENABLED')} />
        ))}
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Application behaviour</div>
        {Object.entries(config.app || {}).map(([k, v]) => (
          <ConfigRow key={k} envKey={k} value={Array.isArray(v) ? v.join(', ') : v} restartRequired={['LOG_FORMAT', 'RATE_LIMIT_ENABLED', 'RATE_LIMIT_IOC_PER_MINUTE', 'RATE_LIMIT_REFRESH_PER_MINUTE'].includes(k)} />
        ))}
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Backup</div>
        {Object.entries(config.backup || {}).map(([k, v]) => (
          <ConfigRow key={k} envKey={k} value={v} />
        ))}
      </div>

      {/* Pending changes sticky bar */}
      {pendingCount > 0 && (
        <div className="pending-bar">
          <span className="pending-bar-info">
            {pendingCount} pending {pendingCount === 1 ? 'change' : 'changes'}:&nbsp;
            <span className="mono" style={{ fontSize: '0.75rem' }}>{Object.keys(queue).join(', ')}</span>
          </span>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={() => setShowDiff(true)}>Review diff</button>
            <button className="admin-btn admin-btn-danger" style={{ fontSize: '0.75rem' }} onClick={() => setQueue({})}>Discard</button>
            <button className="admin-btn admin-btn-primary" style={{ fontSize: '0.75rem' }} onClick={applyAll} disabled={applying}>
              {applying ? <><span className="admin-spinner" /> Applying…</> : 'Write & restart'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
