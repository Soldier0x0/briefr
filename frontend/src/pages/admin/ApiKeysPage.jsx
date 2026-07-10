import { useState, useEffect, useMemo } from 'react'
import { adminApi } from '../../api.js'
import { notifyBackendRestarting } from '../../utils/backendRestart.js'
import HelpTip from './shared/HelpTip.jsx'
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
  { id: 'ingest', title: 'Data sync tuning', backendKey: 'ingest' },
  { id: 'ml', title: 'AI/ML enrichment', backendKey: 'ml' },
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

function saveOutcomeMessage(key, data, restarting, field) {
  if (data?.message) return data.message
  if (restarting) return `${field?.display_label || key} saved — restarting backend`
  if (field?.apply_strategy === 'scheduler_reschedule' && data?.rescheduled_jobs?.length) {
    return `${field?.display_label || key} saved — scheduler rescheduled`
  }
  if (field?.apply_strategy === 'scheduler_reschedule') {
    return `${field?.display_label || key} saved — takes effect after backend restart`
  }
  return `${field?.display_label || key} saved — active now`
}

function applyStrategyBadge(strategy) {
  if (strategy === 'restart') {
    return (
      <span className="badge badge-warn" style={{ fontSize: '0.6rem' }} title="Backend restart required after save">
        restart
      </span>
    )
  }
  if (strategy === 'scheduler_reschedule') {
    return (
      <span className="badge badge-info" style={{ fontSize: '0.6rem' }} title="APScheduler job trigger is rescheduled on save (no full restart)">
        reschedule
      </span>
    )
  }
  return null
}

export default function ApiKeysPage({ toast }) {
  const [config, setConfig] = useState(null)
  const [schema, setSchema] = useState(null)
  const [editing, setEditing] = useState({}) // {key: tempValue}
  const [savingKeys, setSavingKeys] = useState(() => new Set())

  useEffect(() => {
    adminApi.get('/config').then(r => r.json()).then(setConfig).catch(() => {})
    adminApi.get('/config/schema').then(r => r.json()).then(setSchema).catch(() => {})
  }, [])

  async function reloadConfig() {
    try {
      const r = await adminApi.get('/config')
      setConfig(await r.json())
    } catch { /* ignore */ }
  }

  async function saveKey(key, value, field) {
    const error = validateClientSide(field, value)
    if (error) {
      toast(error, false)
      return false
    }

    setSavingKeys(prev => new Set(prev).add(key))
    try {
      const strategy = field?.apply_strategy || (field?.restart_required ? 'restart' : 'immediate')
      const restartRequired = strategy === 'restart'
      let result
      if (restartRequired) {
        result = await adminApi.postJson('/config/apply-all', [{ key, value }])
      } else {
        result = await adminApi.postJson('/config', { key, value })
      }
      const { data } = result

      setEditing(({ [key]: _, ...rest }) => rest)
      await reloadConfig()
      const restarting = restartRequired && (data?.restart_required ?? data?.warning_restart_required)
      if (restarting) notifyBackendRestarting()
      toast(saveOutcomeMessage(key, data, restarting, field), true)
      return true
    } catch (e) {
      toast(`Failed: ${e.message || String(e)}`, false)
      return false
    } finally {
      setSavingKeys(prev => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
    }
  }

  function ConfigRow({ envKey, value, isSecret = false, writable = true, field = null }) {
    const editVal = editing[envKey]
    const isEditing = editVal !== undefined
    const isSaving = savingKeys.has(envKey)
    const label = field?.display_label || envKey
    const strategy = field?.apply_strategy || (field?.restart_required ? 'restart' : 'immediate')
    const restartRequired = strategy === 'restart'
    const helpText = field?.help_text || ''
    const displayValue = (() => {
      const raw = Array.isArray(value) ? value.join(', ') : String(value)
      if (field?.type === 'int' && field?.unit && raw && raw !== 'not configured') {
        return `${raw} ${field.unit}`
      }
      return raw
    })()

    return (
      <div className="config-row">
        <div className="config-row-key mono">
          <span title={envKey}>{label}</span>
          {helpText && <div style={{ fontSize: '0.7rem', color: 'var(--text3)', fontWeight: 400, marginTop: '0.15rem' }}>{helpText}</div>}
          {RATE_LIMIT_HINTS[envKey] && <div style={{ fontSize: '0.7rem', color: 'var(--text3)', fontWeight: 400, marginTop: '0.15rem' }}>{RATE_LIMIT_HINTS[envKey]}</div>}
        </div>
        <div className="config-row-value">
          {!isEditing ? (
            <div className="config-row-value-control">
              {field?.type === 'bool' ? (
                <ToggleSwitch
                  on={value === '1' || value === 'true' || value === true}
                  disabled={isSaving}
                  onChange={v => saveKey(envKey, v ? '1' : '0', field)}
                />
              ) : (
                <span className="mono admin-input admin-input-display" title={isSecret ? undefined : displayValue}>
                  {displayValue}
                </span>
              )}
              <div className="config-row-actions">
                {applyStrategyBadge(strategy)}
                {writable && field?.type !== 'bool' && (
                  <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.7rem', padding: '0.1rem 0.35rem' }}
                    disabled={isSaving}
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
                  disabled={isSaving}
                  onClick={() => saveKey(envKey, editVal, field)}>
                  {isSaving
                    ? <><span className="admin-spinner" /> Saving…</>
                    : (restartRequired ? 'Save & restart' : 'Save')}
                </button>
                <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }}
                  disabled={isSaving}
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

  const fieldsBySection = useMemo(() => {
    const out = {}
    for (const f of schema || []) {
      if (!out[f.section]) out[f.section] = []
      out[f.section].push(f)
    }
    return out
  }, [schema])

  if (!config || !schema) return <div className="admin-empty">Loading…</div>

  const schemaKeys = new Set(schema.map(f => f.key))
  const merged = Object.assign({}, ...SECTIONS.map(s => config[s.backendKey] || {}))

  return (
    <div>
      <h1 className="admin-page-title">
        API keys & config
        <HelpTip text="Changes write to backend/.env and update the running process. Rows tagged restart reload the backend (CORS, DB pool, rate limits). Rows tagged reschedule update APScheduler job triggers without a full restart. Process-level env vars (systemd, secrets manager) override .env and cannot be changed here." />
      </h1>
      <p className="admin-page-subtitle">
        Edit a value and click Save. Most API keys and toggles are
        <span className="badge badge-muted" style={{ fontSize: '0.6rem', margin: '0 0.25rem' }}>immediate</span>.
        Scheduler intervals show
        <span className="badge badge-info" style={{ fontSize: '0.6rem', margin: '0 0.25rem' }}>reschedule</span>
        when the job trigger updates on save. Infrastructure keys show
        <span className="badge badge-warn" style={{ fontSize: '0.6rem', margin: '0 0.25rem' }}>restart</span>
        and restart the backend after save.
      </p>

      {SECTIONS.map(section => {
        const fields = fieldsBySection[section.id] || []
        const backendDict = config[section.backendKey] || {}
        const fieldKeys = new Set(fields.map(f => f.key))
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
    </div>
  )
}
