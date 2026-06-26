import { useState, useEffect, useMemo } from 'react'
import { Search } from 'lucide-react'
import { adminApi } from '../../api.js'
import DiffReviewModal from './shared/DiffReviewModal.jsx'
import ToggleSwitch from './shared/ToggleSwitch.jsx'
import { TIMEZONES_BY_CONTINENT } from '../../utils/timezone.js'
import { RATE_LIMIT_HINTS } from './rateLimits.js'

const TIMEZONE_KEYS = new Set(['SCHEDULER_TIMEZONE', 'CORRELATION_TIMEZONE', 'OTX_CORRELATION_TIMEZONE', 'DEFAULT_TIMEZONE'])

const SECTIONS = [
  { id: 'api_keys', title: 'API keys & credentials', backendKey: 'api_keys', defaultOpen: true },
  { id: 'webhooks', title: 'Webhooks — Discord, Telegram, generic', backendKey: 'webhooks', defaultOpen: true },
  { id: 'scheduler_main', title: 'Scheduler — NVD, KEV, EPSS intervals', backendKey: 'scheduler' },
  { id: 'scheduler_cron', title: 'Scheduler — cron expressions & timezone', backendKey: 'scheduler' },
  { id: 'ingest', title: 'Ingest tuning', backendKey: 'ingest' },
  { id: 'ml', title: 'ML toggles', backendKey: 'ml' },
  { id: 'app', title: 'Application behaviour', backendKey: 'app' },
  { id: 'backup', title: 'Backup', backendKey: 'backup' },
]

const HUMAN_LABELS = {
  NVD_API_KEY: 'NVD API key',
  NVD_DAYS_BACK: 'NVD lookback window (days)',
  VIRUSTOTAL_API_KEY: 'VirusTotal API key',
  ABUSEIPDB_API_KEY: 'AbuseIPDB API key',
  GREYNOISE_API_KEY: 'GreyNoise API key',
  GITHUB_TOKEN: 'GitHub token',
  OPENAI_API_KEY: 'OpenAI API key',
  OTX_API_KEY: 'AlienVault OTX API key',
  DISCORD_WEBHOOK_URL: 'Discord webhook URL',
  TELEGRAM_BOT_TOKEN: 'Telegram bot token',
  TELEGRAM_CHAT_ID: 'Telegram chat ID',
  GENERIC_WEBHOOK_URL: 'Generic webhook URL',
  BRIEFR_STACK_TERMS: 'Stack filter terms (BRIEF)',
  SCHEDULER_TIMEZONE: 'Scheduler timezone',
  DEFAULT_TIMEZONE: 'Default display timezone',
}

function humanizeConfigKey(key) {
  if (HUMAN_LABELS[key]) return HUMAN_LABELS[key]
  return key
    .split('_')
    .map((part, i) => (i === 0 ? part.charAt(0) + part.slice(1).toLowerCase() : part.toLowerCase()))
    .join(' ')
}

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

function isConfigTruthy(value) {
  if (value === true || value === 1) return true
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    return normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on'
  }
  return false
}

function matchesSearch(query, field, humanTitle) {
  if (!query) return true
  const q = query.toLowerCase()
  return (
    field.key.toLowerCase().includes(q)
    || humanTitle.toLowerCase().includes(q)
    || (field.help_text || '').toLowerCase().includes(q)
  )
}

export default function ApiKeysPage({ toast }) {
  const [config, setConfig] = useState(null)
  const [schema, setSchema] = useState(null)
  const [queue, setQueue] = useState({})
  const [editing, setEditing] = useState({})
  const [showDiff, setShowDiff] = useState(false)
  const [applying, setApplying] = useState(false)
  const [search, setSearch] = useState('')

  useEffect(() => {
    adminApi.get('/config').then(r => r.json()).then(setConfig).catch(() => {})
    adminApi.get('/config/schema').then(r => r.json()).then(setSchema).catch(() => {})
  }, [])

  function addToQueue(key, value, field) {
    const error = validateClientSide(field, value)
    if (error) { toast(error, false); return }
    setQueue(q => ({ ...q, [key]: value }))
    setEditing(({ [key]: _, ...rest }) => rest)
    toast(`Queued change for ${humanizeConfigKey(key)}`, true)
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

  function ConfigField({ envKey, value, isSecret = false, writable = true, restartRequired = false, helpText = '', field = null }) {
    const inQueue = queue[envKey] !== undefined
    const editVal = editing[envKey]
    const isEditing = editVal !== undefined
    const humanTitle = humanizeConfigKey(envKey)

    return (
      <div className="admin-config-field config-row">
        <div className="admin-config-field-label config-row-key">
          <div className="admin-config-field-title">{humanTitle}</div>
          <div className="admin-config-field-key mono">{envKey}</div>
          {helpText && <div className="admin-config-field-help">{helpText}</div>}
          {RATE_LIMIT_HINTS[envKey] && <div className="admin-config-field-help">{RATE_LIMIT_HINTS[envKey]}</div>}
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
                <button type="button" className="admin-btn admin-btn-ghost admin-btn--sm" onClick={() => removeFromQueue(envKey)}>×</button>
              </div>
            </div>
          ) : !isEditing ? (
            <div className="config-row-value-control">
              {field?.type === 'bool' ? (
                <ToggleSwitch
                  on={isConfigTruthy(value)}
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
                  <button
                    type="button"
                    className="admin-btn admin-btn-ghost admin-btn--sm"
                    onClick={() => {
                      const initial = isSecret ? '' : (Array.isArray(value) ? value.join(', ') : (value === 'not configured' ? '' : String(value)))
                      setEditing(e => ({ ...e, [envKey]: initial }))
                    }}
                  >
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
                <button type="button" className="admin-btn admin-btn-primary admin-btn--sm" onClick={() => addToQueue(envKey, editVal, field)}>
                  Queue change
                </button>
                <button type="button" className="admin-btn admin-btn-ghost admin-btn--sm" onClick={() => setEditing(({ [envKey]: _, ...rest }) => rest)}>
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
    if (!schema) return {}
    const map = {}
    for (const f of schema) {
      if (!map[f.section]) map[f.section] = []
      map[f.section].push(f)
    }
    return map
  }, [schema])

  if (!config || !schema) return <div className="admin-loading"><span className="admin-spinner" /> Loading configuration…</div>

  const pendingCount = Object.keys(queue).length
  const schemaKeys = new Set(schema.map(f => f.key))
  const merged = Object.assign({}, ...SECTIONS.map(s => config[s.backendKey] || {}))
  const query = search.trim()

  const visibleSections = SECTIONS.map(section => {
    const fields = (fieldsBySection[section.id] || []).filter(f => matchesSearch(query, f, humanizeConfigKey(f.key)))
    const backendDict = config[section.backendKey] || {}
    const fieldKeys = new Set((fieldsBySection[section.id] || []).map(f => f.key))
    const extraKeys = (section.id === 'ml' || section.id === 'backup')
      ? Object.keys(backendDict).filter(k => !fieldKeys.has(k) && !schemaKeys.has(k) && (!query || k.toLowerCase().includes(query.toLowerCase())))
      : []
    return { section, fields, extraKeys, backendDict, count: fields.length + extraKeys.length }
  }).filter(s => s.count > 0)

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

      <header className="admin-page-header">
        <h1 className="admin-page-title">
          API keys & config
          <span
            className="info-tip"
            tabIndex={0}
            title="Process environment variables win over .env. Changes here write to .env and usually need a restart."
          >ⓘ</span>
        </h1>
        <p className="admin-page-subtitle">
          Secrets and tunables the backend reads from .env. Search by friendly name or env key.
        </p>
      </header>

      <div className="admin-config-toolbar">
        <div className="admin-config-search">
          <Search size={14} aria-hidden />
          <input
            type="search"
            placeholder="Search settings…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Search configuration settings"
          />
        </div>
        {pendingCount > 0 && (
          <span className="badge badge-warn">{pendingCount} pending</span>
        )}
      </div>

      {visibleSections.length === 0 ? (
        <div className="admin-config-empty">No settings match your search.</div>
      ) : (
        visibleSections.map(({ section, fields, extraKeys, backendDict }) => (
          <details key={section.id} className="admin-config-category" open={section.defaultOpen ?? !query}>
            <summary>
              {section.title}
              <span className="admin-config-category-count">{fields.length + extraKeys.length}</span>
            </summary>
            <div className="admin-config-grid config-grid">
              {fields.map(f => (
                <ConfigField
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
                <ConfigField key={k} envKey={k} value={backendDict[k]} writable={false} />
              ))}
            </div>
            {section.id === 'webhooks' && (
              <p className="admin-text-muted" style={{ fontSize: 11, padding: '0 16px 14px' }}>
                After setting a URL or token, use the Test button on the Webhooks page to confirm delivery.
              </p>
            )}
          </details>
        ))
      )}

      {pendingCount > 0 && (
        <div className="pending-bar">
          <span className="pending-bar-info">
            {pendingCount} pending {pendingCount === 1 ? 'change' : 'changes'} ready to write
          </span>
          <div className="admin-btn-row" style={{ marginTop: 0 }}>
            <button type="button" className="admin-btn admin-btn-ghost admin-btn--sm" onClick={() => setShowDiff(true)}>Review diff</button>
            <button type="button" className="admin-btn admin-btn-danger admin-btn--sm" onClick={() => setQueue({})}>Discard</button>
            <button type="button" className="admin-btn admin-btn-primary admin-btn--sm" onClick={applyAll} disabled={applying}>
              {applying ? <><span className="admin-spinner" /> Applying…</> : 'Write & restart'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
