import { useState, useEffect } from 'react'
import { adminApi } from '../../api.js'
import DiffReviewModal from './shared/DiffReviewModal.jsx'
import ToggleSwitch from './shared/ToggleSwitch.jsx'
import { TIMEZONES_BY_CONTINENT } from '../../utils/timezone.js'
import { RATE_LIMIT_HINTS } from './rateLimits.js'

const TIMEZONE_KEYS = new Set(['SCHEDULER_TIMEZONE', 'CORRELATION_TIMEZONE', 'OTX_CORRELATION_TIMEZONE', 'DEFAULT_TIMEZONE'])

// UI section -> { title, backendKey } — backendKey is which dict in the
// GET /api/admin/config response actually holds these values (a few
// schema "sections" are UI-only groupings within one backend dict, e.g.
// scheduler_main/scheduler_cron both read from config.scheduler).
const SECTIONS = [
  { id: 'api_keys', title: 'API Keys', backendKey: 'api_keys' },
  { id: 'webhooks', title: 'Webhooks — Discord / Telegram / generic', backendKey: 'webhooks' },
  { id: 'scheduler_main', title: 'Scheduler intervals — NVD / KEV / EPSS', backendKey: 'scheduler' },
  { id: 'scheduler_cron', title: 'Scheduler intervals — cron & timezone', backendKey: 'scheduler' },
  { id: 'ingest', title: 'Ingest tuning', backendKey: 'ingest' },
  { id: 'ml', title: 'ML toggles', backendKey: 'ml' },
  { id: 'app', title: 'Application behaviour', backendKey: 'app' },
  { id: 'backup', title: 'Backup', backendKey: 'backup' },
]

function validateClientSide(field, value) {
  if (!field) return null
  if (field.type === 'int') {
    const parsed = Number(value)
    if (!Number.isInteger(parsed)) return `${field.key} requires an integer value`
    if (field.min != null && parsed < field.min) return `${field.key} must be >= ${field.min}`
    if (field.max != null && parsed > field.max) return `${field.key} must be <= ${field.max}`
  } else if (field.type === 'enum' && field.enum_values?.length) {
    if (!field.enum_values.includes(value)) return `${field.key} must be one of: ${field.enum_values.join(', ')}`
  }
  return null
}

export default function ApiKeysPage({ toast }) {
  const [config, setConfig] = useState(null)
  const [schema, setSchema] = useState(null)
  const [queue, setQueue] = useState({}) // {key: value}
  const [editing, setEditing] = useState({}) // {key: tempValue}
  const [showDiff, setShowDiff] = useState(false)
  const [applying, setApplying] = useState(false)

  useEffect(() => {
    adminApi.get('/config').then(r => r.json()).then(setConfig).catch(() => {})
    adminApi.get('/config/schema').then(r => r.json()).then(setSchema).catch(() => {})
  }, [])

  function addToQueue(key, value, field) {
    const error = validateClientSide(field, value)
    if (error) { toast(error, false); return }
    setQueue(q => ({ ...q, [key]: value }))
    setEditing(({ [key]: _, ...rest }) => rest)
    toast(`Added ${key} to pending changes`, true)
  }

  function removeFromQueue(key) {
    setQueue(({ [key]: _, ...rest }) => rest)
  }

  async function applyAll() {
    const items = Object.entries(queue).map(([key, value]) => ({ key, value }))
    setApplying(true)
    try {
      const res = await adminApi.post('/config/apply-all', items)
      const data = await res.json()
      if (res.ok) {
        toast(data.message || `Applied ${data.changed_keys?.length} changes.`, true)
        setQueue({})
      } else {
        const errs = data.errors || [data.detail]
        toast(`Failed: ${errs.join('; ')}`, false)
      }
    } catch (e) { toast(String(e.message), false) }
    setApplying(false)
  }

  function ConfigRow({ envKey, value, isSecret = false, writable = true, restartRequired = false, helpText = '', field = null }) {
    const inQueue = queue[envKey] !== undefined
    const editVal = editing[envKey]
    const isEditing = editVal !== undefined

    return (
      <div className="config-row">
        <div className="config-row-key mono">
          {envKey}
          {helpText && <div style={{ fontSize: '0.7rem', color: 'var(--text3)', fontWeight: 400, marginTop: '0.15rem' }}>{helpText}</div>}
          {RATE_LIMIT_HINTS[envKey] && <div style={{ fontSize: '0.7rem', color: 'var(--text3)', fontWeight: 400, marginTop: '0.15rem' }}>{RATE_LIMIT_HINTS[envKey]}</div>}
        </div>
        <div className="config-row-value">
          {inQueue ? (
            <div className="config-row-value-control">
              <span className="badge badge-warn">
                queued: {isSecret
                  ? '••••'
                  : field?.type === 'bool'
                    ? ((queue[envKey] === '1' || queue[envKey] === 'true') ? 'Enabled' : 'Disabled')
                    : queue[envKey]}
              </span>
              <div className="config-row-actions">
                <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.7rem' }} onClick={() => removeFromQueue(envKey)}>×</button>
              </div>
            </div>
          ) : !isEditing ? (
            <div className="config-row-value-control">
              {field?.type === 'bool' ? (
                <ToggleSwitch
                  on={value === '1' || value === 'true' || value === true}
                  onChange={v => addToQueue(envKey, v ? '1' : '0', field)}
                />
              ) : (
                <span className="mono admin-input admin-input-display" title={isSecret ? undefined : (Array.isArray(value) ? value.join(', ') : String(value))}>
                  {Array.isArray(value) ? value.join(', ') : String(value)}
                </span>
              )}
              <div className="config-row-actions">
                {restartRequired && <span className="badge badge-warn" style={{ fontSize: '0.6rem' }}>restart</span>}
                {writable && field?.type !== 'bool' && (
                  <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.7rem', padding: '0.1rem 0.35rem' }}
                    onClick={() => {
                      const initial = isSecret ? '' : (Array.isArray(value) ? value.join(', ') : (value === 'not configured' ? '' : String(value)))
                      setEditing(e => ({ ...e, [envKey]: initial }))
                    }}>
                    Edit
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="config-row-value-control config-row-value-control--edit">
              {field?.type === 'enum' && field.enum_values?.length ? (
                <select
                  className="admin-select config-row-input"
                  value={editVal}
                  onChange={e => setEditing(ed => ({ ...ed, [envKey]: e.target.value }))}
                  autoFocus
                >
                  {field.enum_values.map(v => <option key={v} value={v}>{v}</option>)}
                </select>
              ) : TIMEZONE_KEYS.has(envKey) ? (
                <select
                  className="admin-select config-row-input"
                  value={editVal}
                  onChange={e => setEditing(ed => ({ ...ed, [envKey]: e.target.value }))}
                  autoFocus
                >
                  {editVal && !TIMEZONES_BY_CONTINENT.some(g => g.zones.some(z => z.tz === editVal)) && (
                    <option value={editVal}>{editVal} (current)</option>
                  )}
                  {TIMEZONES_BY_CONTINENT.map(group => (
                    <optgroup key={group.continent} label={group.continent}>
                      {group.zones.map(z => <option key={z.tz} value={z.tz}>{z.label}</option>)}
                    </optgroup>
                  ))}
                </select>
              ) : (
                <input
                  className="admin-input config-row-input"
                  type={isSecret ? 'password' : 'text'}
                  value={editVal}
                  onChange={e => setEditing(ed => ({ ...ed, [envKey]: e.target.value }))}
                  autoFocus
                />
              )}
              <div className="config-row-actions">
                <button className="admin-btn admin-btn-primary" style={{ fontSize: '0.75rem' }}
                  onClick={() => addToQueue(envKey, editVal, field)}>
                  Add to queue
                </button>
                <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }}
                  onClick={() => setEditing(({ [envKey]: _, ...rest }) => rest)}>
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  if (!config || !schema) return <div className="admin-empty">Loading…</div>

  const pendingCount = Object.keys(queue).length
  const fieldsBySection = {}
  for (const f of schema) {
    if (!fieldsBySection[f.section]) fieldsBySection[f.section] = []
    fieldsBySection[f.section].push(f)
  }
  const schemaKeys = new Set(schema.map(f => f.key))
  // A handful of writable keys live under a different backend response dict
  // than their UI grouping (e.g. VULNRICHMENT_BRANCH/CVELISTV5_BRANCH are
  // grouped under "Ingest tuning" but the backend returns them inside
  // config.scheduler) — look values up across every section rather than
  // assuming a 1:1 mapping between UI section and backend dict.
  const merged = Object.assign({}, ...SECTIONS.map(s => config[s.backendKey] || {}))

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

      <h1 className="admin-page-title">
        API keys & config
        <span
          className="info-tip"
          tabIndex={0}
          title="load_dotenv() is called without override=True — process env vars (systemd / Cursor Secrets) win over .env. Changes here write to .env and take effect after restart."
        >ⓘ</span>
      </h1>
      <p className="admin-page-subtitle">
        Sets secrets and tunables that the backend reads from .env. Most changes need a restart to take effect.
      </p>

      {SECTIONS.map(section => {
        const fields = fieldsBySection[section.id] || []
        const backendDict = config[section.backendKey] || {}
        const fieldKeys = new Set(fields.map(f => f.key))
        // ml/backup sections historically also surfaced a few read-only,
        // non-writable keys (e.g. feed sync toggles, backup log rotation
        // settings) that aren't in the schema — keep showing them
        // (read-only, no broken Edit button) instead of silently dropping
        // visibility into values the operator could previously see.
        const extraKeys = (section.id === 'ml' || section.id === 'backup')
          ? Object.keys(backendDict).filter(k => !fieldKeys.has(k) && !schemaKeys.has(k))
          : []

        if (fields.length === 0 && extraKeys.length === 0) return null

        return (
          <div className="admin-card" key={section.id}>
            <div className="admin-card-title">{section.title}</div>
            <div className="config-grid">
              {fields.map(f => (
                <ConfigRow
                  key={f.key}
                  envKey={f.key}
                  value={merged[f.key] ?? ''}
                  isSecret={f.type === 'secret'}
                  restartRequired={f.restart_required}
                  helpText={f.help_text}
                  field={f}
                />
              ))}
              {extraKeys.map(k => (
                <ConfigRow key={k} envKey={k} value={backendDict[k]} writable={false} />
              ))}
            </div>
            {section.id === 'webhooks' && (
              <div style={{ fontSize: '0.75rem', color: 'var(--text3)', marginTop: '0.5rem' }}>
                After setting a URL/token here, use the Test button on the Webhooks page to confirm delivery.
              </div>
            )}
          </div>
        )
      })}

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
