import { useState, useEffect, useMemo, useCallback } from 'react'
import { adminApi } from '../../api.js'
import { Select, SelectGroup, SelectItem, SelectLabel } from '../../components/ui/index.js'
import { notifyBackendRestarting } from '../../utils/backendRestart.js'
import HelpTip from './shared/HelpTip.jsx'
import ToggleSwitch from './shared/ToggleSwitch.jsx'
import DiffReviewModal from './shared/DiffReviewModal.jsx'
import ApiKeyHealthPanel from './ApiKeyHealthPanel.jsx'
import SearchTokensPanel from './SearchTokensPanel.jsx'
import { AdminPageSkeleton } from './shared/AdminSkeletons.jsx'
import { TIMEZONES_BY_CONTINENT } from '../../utils/timezone.js'
import { RATE_LIMIT_HINTS } from './rateLimits.js'

const SECTION_EXPAND_KEY = 'briefr-config-sections'

const TIMEZONE_KEYS = new Set(['SCHEDULER_TIMEZONE', 'CORRELATION_TIMEZONE', 'OTX_CORRELATION_TIMEZONE', 'DEFAULT_TIMEZONE'])

// UI section -> { title, backendKey } — backendKey is which dict in the
// GET /api/admin/config response actually holds these values (a few
// schema "sections" are UI-only groupings within one backend dict, e.g.
// scheduler_main/scheduler_cron both read from config.scheduler).
const SECTIONS = [
  { id: 'api_keys', title: 'API Keys', backendKey: 'api_keys' },
  { id: 'security', title: 'Security / kiosk', backendKey: 'security' },
  { id: 'webhooks', title: 'Webhooks — Discord / Telegram / generic', backendKey: 'webhooks' },
  { id: 'scheduler_main', title: 'Scheduler intervals — NVD / KEV / EPSS', backendKey: 'scheduler' },
  { id: 'scheduler_cron', title: 'Scheduler intervals — cron & timezone', backendKey: 'scheduler' },
  { id: 'ingest', title: 'Data sync tuning', backendKey: 'ingest' },
  { id: 'ml', title: 'AI/ML enrichment', backendKey: 'ml' },
  { id: 'queue', title: 'Durable jobs & metering', backendKey: 'queue' },
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

function MeteringColumn({ title, rows }) {
  const max = Math.max(1, ...rows.map(r => r.calls || 0))
  return (
    <div>
      <p className="metering-col-title mono">{title}</p>
      {rows.length === 0 ? (
        <p className="metering-empty mono">No events yet</p>
      ) : (
        <ul className="metering-list">
          {rows.map(row => (
            <li key={row.key} className="metering-row">
              <span className="metering-row-label">
                <span className="metering-row-name mono">{row.name}</span>
                {row.meta && <span className="metering-row-meta">{row.meta}</span>}
              </span>
              <span className="metering-bar-track">
                <span className="metering-bar-fill" style={{ width: `${((row.calls || 0) / max) * 100}%` }} />
              </span>
              <span className="metering-row-count mono">{row.calls || 0}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function ApiKeysPage({ toast }) {
  const [config, setConfig] = useState(null)
  const [schema, setSchema] = useState(null)
  const [editing, setEditing] = useState({}) // {key: tempValue}
  const [savingKeys, setSavingKeys] = useState(() => new Set())
  const [expandedSections, setExpandedSections] = useState(() => {
    try {
      const raw = localStorage.getItem(SECTION_EXPAND_KEY)
      if (raw) {
        const parsed = JSON.parse(raw)
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          return parsed
        }
      }
    } catch { /* ignore */ }
    return { api_keys: true }
  })
  const [showReview, setShowReview] = useState(false)
  const [applyingAll, setApplyingAll] = useState(false)
  const [health, setHealth] = useState(null)
  const [healthLoading, setHealthLoading] = useState(true)
  const [healthError, setHealthError] = useState(null)
  const [healthRunning, setHealthRunning] = useState(false)
  const [metering, setMetering] = useState(null)
  const [meteringError, setMeteringError] = useState(null)
  const [meteringLoading, setMeteringLoading] = useState(true)

  const sectionOpen = useCallback((sectionId) => (
    expandedSections[sectionId] ?? (sectionId === 'api_keys')
  ), [expandedSections])

  const toggleSection = useCallback((sectionId) => {
    setExpandedSections((prev) => {
      const next = { ...prev, [sectionId]: !(prev[sectionId] ?? (sectionId === 'api_keys')) }
      try { localStorage.setItem(SECTION_EXPAND_KEY, JSON.stringify(next)) } catch { /* ignore */ }
      return next
    })
  }, [])

  useEffect(() => {
    adminApi.get('/config').then(r => r.json()).then(setConfig).catch(() => {})
    adminApi.get('/config/schema').then(r => r.json()).then(setSchema).catch(() => {})
  }, [])

  const loadHealth = useCallback(async () => {
    setHealthLoading(true)
    setHealthError(null)
    try {
      const res = await adminApi.get('/api-keys/health')
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${res.status}`)
      }
      setHealth(await res.json())
    } catch (e) {
      setHealthError(e)
      setHealth(null)
    } finally {
      setHealthLoading(false)
    }
  }, [])

  useEffect(() => {
    loadHealth()
  }, [loadHealth])

  useEffect(() => {
    let cancelled = false
    setMeteringLoading(true)
    adminApi.get('/api-usage/metering?hours=24')
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((body) => {
        if (!cancelled) {
          setMetering(body)
          setMeteringError(null)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setMetering(null)
          setMeteringError(e?.message || 'Metering unavailable')
        }
      })
      .finally(() => {
        if (!cancelled) setMeteringLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const runHealthCheck = useCallback(async () => {
    setHealthRunning(true)
    try {
      const { data } = await adminApi.postJson('/api-keys/health/run', {})
      setHealth({
        providers: data.providers || [],
        configured_count: data.configured_count,
        healthy_count: data.healthy_count,
        checked_at: data.checked_at,
      })
      const checked = data.stats?.checked ?? data.configured_count ?? 0
      const healthy = data.stats?.healthy ?? data.healthy_count ?? 0
      toast(`Health check complete — ${healthy}/${checked} configured providers healthy`, true)
    } catch (e) {
      toast(`Health check failed: ${e.message || String(e)}`, false)
    } finally {
      setHealthRunning(false)
    }
  }, [toast])

  const healthByEnvKey = useMemo(() => {
    const map = {}
    for (const row of health?.providers || []) {
      map[row.env_key] = row
    }
    return map
  }, [health])

  async function reloadConfig() {
    try {
      const r = await adminApi.get('/config')
      setConfig(await r.json())
    } catch { /* ignore */ }
  }

  const fieldByKey = useMemo(() => {
    const map = {}
    for (const f of schema || []) map[f.key] = f
    return map
  }, [schema])

  async function applyPendingChanges(pending = editing) {
    const entries = Object.entries(pending).filter(([key, value]) => {
      const field = fieldByKey[key]
      if (field?.type === 'secret' && String(value).trim() === '') {
        return false
      }
      return true
    })
    if (!entries.length) {
      toast('No changes to apply (blank secret fields are skipped)', false)
      return
    }

    for (const [key, value] of entries) {
      const err = validateClientSide(fieldByKey[key], value)
      if (err) {
        toast(err, false)
        return
      }
    }

    setApplyingAll(true)
    try {
      const body = entries.map(([key, value]) => ({ key, value }))
      const { data } = await adminApi.postJson('/config/apply-all', body)
      setEditing({})
      await reloadConfig()
      if (data?.restart_required ?? data?.warning_restart_required) {
        notifyBackendRestarting()
      }
      toast(data?.message || `Applied ${entries.length} change(s)`, true)
      setShowReview(false)
    } catch (e) {
      toast(`Apply failed: ${e.message || String(e)}`, false)
    } finally {
      setApplyingAll(false)
    }
  }

  const pendingCount = Object.keys(editing).length

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
    const healthRow = healthByEnvKey[envKey]
    const keySuffix = isSecret && healthRow?.key_suffix ? healthRow.key_suffix : null
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
                  {keySuffix && (
                    <span className="config-key-suffix mono" title="Key suffix from health check">
                      {' '}
                      (
                      {keySuffix}
                      )
                    </span>
                  )}
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
                <Select
                  className="admin-select config-row-input"
                  value={editVal}
                  onChange={(v) => setEditing(ed => ({ ...ed, [envKey]: v }))}
                  options={field.enum_values.map(v => ({ value: v, label: v }))}
                  autoFocus
                />
              ) : TIMEZONE_KEYS.has(envKey) ? (
                <Select
                  className="admin-select config-row-input"
                  value={editVal}
                  onChange={(v) => setEditing(ed => ({ ...ed, [envKey]: v }))}
                  autoFocus
                >
                  {editVal && !TIMEZONES_BY_CONTINENT.some(g => g.zones.some(z => z.tz === editVal)) && (
                    <SelectItem value={editVal}>{editVal} (current)</SelectItem>
                  )}
                  {TIMEZONES_BY_CONTINENT.map(group => (
                    <SelectGroup key={group.continent}>
                      <SelectLabel>{group.continent}</SelectLabel>
                      {group.zones.map(z => (
                        <SelectItem key={z.tz} value={z.tz}>{z.label}</SelectItem>
                      ))}
                    </SelectGroup>
                  ))}
                </Select>
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

  if (!config || !schema) return <AdminPageSkeleton variant="form" />

  const schemaKeys = new Set(schema.map(f => f.key))
  const merged = Object.assign({}, ...SECTIONS.map(s => config[s.backendKey] || {}))

  return (
    <div>
      <h1 className="admin-page-title">
        API keys & config
        <HelpTip text="Changes save to the database and update the running process — backend/.env is no longer written to. Rows tagged restart reload the backend (CORS, DB pool, rate limits). Rows tagged reschedule update APScheduler job triggers without a full restart. Process-level env vars (systemd, secrets manager) always win and cannot be changed here." />
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

      <ApiKeyHealthPanel
        health={health}
        loading={healthLoading}
        error={healthError}
        running={healthRunning}
        onRefresh={loadHealth}
        onRun={runHealthCheck}
      />

      <SearchTokensPanel toast={toast} />

      <div className="admin-card" style={{ marginBottom: 'var(--space-4)' }}>
        <div className="admin-card-header">
          <div className="admin-card-title">
            Outbound API metering (24h)
            <HelpTip text="Every resilient_request attempt is counted, including retries. Rollups come from api_usage; the actor breakdown comes from api_call_events." />
          </div>
        </div>
        <div className="admin-card-body">
          {meteringLoading && <p className="metering-empty mono">Loading metering…</p>}
          {!meteringLoading && meteringError && (
            <p className="metering-empty mono" style={{ color: 'var(--status-error)' }}>{meteringError}</p>
          )}
          {!meteringLoading && !meteringError && metering && (
            <div className="metering-cols">
              <MeteringColumn
                title="BY SOURCE"
                rows={(metering.by_source || []).slice(0, 8).map(row => ({
                  key: row.source,
                  name: row.source,
                  calls: row.calls,
                  meta: row.last_called_at ? `last ${new Date(row.last_called_at).toLocaleString()}` : null,
                }))}
              />
              <MeteringColumn
                title="BY ACTOR"
                rows={(metering.by_actor || []).map(row => ({
                  key: row.actor_type,
                  name: row.actor_type,
                  calls: row.calls,
                }))}
              />
            </div>
          )}
        </div>
      </div>

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
            <div
              className="config-section-header"
              role="button"
              tabIndex={0}
              onClick={() => toggleSection(section.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  toggleSection(section.id)
                }
              }}
            >
              <div className="admin-card-title" style={{ margin: 0 }}>{section.title}</div>
              <span className="config-section-chevron" aria-hidden>{sectionOpen(section.id) ? '▼' : '▶'}</span>
            </div>
            {sectionOpen(section.id) && (
            <div className="config-grid" style={{ marginTop: '0.75rem' }}>
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
            )}
            {sectionOpen(section.id) && section.id === 'webhooks' && (
              <div style={{ fontSize: '0.75rem', color: 'var(--text3)', marginTop: '0.5rem', padding: '0.5rem 0.65rem', border: '1px solid var(--border)', borderRadius: '4px' }}>
                <strong>Legacy bootstrap:</strong> values here seed the default <code className="mono">discord</code>, <code className="mono">telegram</code>, and <code className="mono">generic</code> destinations at startup.
                Add more endpoints, edit event subscriptions, and run delivery tests on the <strong>Webhooks</strong> admin tab.
              </div>
            )}
          </div>
        )
      })}

      {pendingCount > 0 && (
        <div className="config-apply-bar" role="region" aria-label="Pending configuration changes">
          <span style={{ fontSize: '0.8125rem', color: 'var(--text2)' }}>
            <strong>{pendingCount}</strong> pending change{pendingCount !== 1 ? 's' : ''}
          </span>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button type="button" className="admin-btn admin-btn-ghost" disabled={applyingAll}
              onClick={() => setEditing({})}>
              Discard
            </button>
            <button type="button" className="admin-btn admin-btn-ghost" disabled={applyingAll}
              onClick={() => setShowReview(true)}>
              Review
            </button>
            <button type="button" className="admin-btn admin-btn-primary" disabled={applyingAll}
              onClick={() => applyPendingChanges()}>
              {applyingAll ? <><span className="admin-spinner" /> Applying…</> : 'Apply all'}
            </button>
          </div>
        </div>
      )}

      {showReview && (
        <DiffReviewModal
          title="Review pending configuration changes"
          changes={editing}
          secretKeyPredicate={(k) => fieldByKey[k]?.type === 'secret'}
          applying={applyingAll}
          applyLabel="Apply all"
          onApply={() => applyPendingChanges()}
          onDiscard={() => { setEditing({}); setShowReview(false) }}
          onClose={() => setShowReview(false)}
        />
      )}
    </div>
  )
}
