import { useState, useEffect, useCallback, Fragment } from 'react'
import { adminApi, fetchUserStack } from '../../api.js'
import { fmtIso } from './formatters.js'
import AsyncSection from './shared/AsyncSection.jsx'
import ConfirmModal from './shared/ConfirmModal.jsx'
import HelpTip from './shared/HelpTip.jsx'
import ToggleSwitch from './shared/ToggleSwitch.jsx'

const EVENT_OPTIONS = [
  { id: 'kev_alert', label: 'KEV stack match' },
  { id: 'kev_backlog', label: 'KEV detection backlog' },
  { id: 'watchlist_alert', label: 'Watchlist (pinned CVE)' },
  { id: 'ioc_watchlist_hit', label: 'IOC watchlist hit' },
  { id: 'backup_failure', label: 'Backup failure' },
  { id: 'health', label: 'Health / test' },
]

const KIND_OPTIONS = ['discord', 'telegram', 'generic']

const EMPTY_CREATE = {
  kind: 'discord',
  id: '',
  label: '',
  url: '',
  token: '',
  chat_id: '',
  enabled: true,
  event_types: EVENT_OPTIONS.map(e => e.id),
}

function sourceBadge(source) {
  if (source === 'env') {
    return <span className="badge badge-info" title="Bootstrapped from .env — disable here; secrets stay on API keys page">env</span>
  }
  return <span className="badge badge-muted" title="Created in BRIEFR — config stored in database">db</span>
}

function configSummary(dest) {
  const cfg = dest.config || {}
  if (dest.kind === 'telegram') {
    const parts = []
    if (cfg.token) parts.push(`token: ${cfg.token}`)
    if (cfg.chat_id) parts.push(`chat: ${cfg.chat_id}`)
    return parts.join(' · ') || '—'
  }
  if (cfg.url) return cfg.url
  return '—'
}

export default function WebhooksPage({ toast }) {
  const [destinations, setDestinations] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [userStack, setUserStack] = useState('')
  const [envStack, setEnvStack] = useState('')
  const [results, setResults] = useState({})
  const [testing, setTesting] = useState({})
  const [saving, setSaving] = useState({})
  const [expanded, setExpanded] = useState({})
  const [eventDraft, setEventDraft] = useState({})
  const [configDraft, setConfigDraft] = useState({})
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState(EMPTY_CREATE)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [log, setLog] = useState(null)
  const [logOffset, setLogOffset] = useState(0)
  const logLimit = 50

  const loadDestinations = useCallback(async () => {
    try {
      const { data } = await adminApi.getJson('/webhooks/destinations')
      setDestinations(data.destinations || [])
      setLoadError(null)
    } catch (e) {
      setLoadError(e)
    }
  }, [])

  useEffect(() => {
    loadDestinations()
    adminApi.get('/config').then(r => r.json()).then(c => {
      setEnvStack((c?.app?.BRIEFR_STACK_TERMS || '').trim())
    }).catch(() => {})
    fetchUserStack().then(d => setUserStack(d?.stack_terms || '')).catch(() => {})
  }, [loadDestinations])

  async function loadLog(offset = 0) {
    try {
      const res = await adminApi.get(`/webhooks/log?limit=${logLimit}&offset=${offset}`)
      setLog(await res.json())
      setLogOffset(offset)
    } catch { /* ignore */ }
  }

  useEffect(() => { loadLog() }, [])

  async function testDestination(destinationId) {
    setTesting(t => ({ ...t, [destinationId]: true }))
    try {
      const res = await adminApi.post('/config/webhook-test', { destination_id: destinationId })
      const data = await res.json()
      setResults(r => ({ ...r, [destinationId]: data }))
      const ref = res.headers.get('X-Request-ID')
      const refNote = ref ? ` (ref: ${ref})` : ''
      toast(
        data.ok ? `${destinationId} delivered${refNote}` : `${destinationId} failed: ${data.error}${refNote}`,
        data.ok,
      )
    } catch (e) {
      toast(String(e.message), false)
    }
    setTesting(t => ({ ...t, [destinationId]: false }))
  }

  async function patchDestination(id, body, label = 'Saved') {
    setSaving(s => ({ ...s, [id]: true }))
    try {
      await adminApi.patchJson(`/webhooks/destinations/${id}`, body)
      await loadDestinations()
      toast(label, true)
      return true
    } catch (e) {
      toast(`Failed: ${e.message}`, false)
      return false
    } finally {
      setSaving(s => ({ ...s, [id]: false }))
    }
  }

  async function toggleEnabled(dest, enabled) {
    await patchDestination(dest.id, { enabled }, enabled ? 'Destination enabled' : 'Destination disabled')
  }

  async function saveEventTypes(dest) {
    const draft = eventDraft[dest.id]
    if (!draft) return
    const ok = await patchDestination(dest.id, { event_types: draft }, 'Event subscriptions updated')
    if (ok) setExpanded(e => ({ ...e, [dest.id]: false }))
  }

  async function saveConfig(dest) {
    const draft = configDraft[dest.id]
    if (!draft) return
    const config = dest.kind === 'telegram'
      ? { token: draft.token, chat_id: draft.chat_id }
      : { url: draft.url }
    const ok = await patchDestination(dest.id, { config }, 'Destination config updated')
    if (ok) setExpanded(e => ({ ...e, [`cfg-${dest.id}`]: false }))
  }

  async function createDestination() {
    setSaving(s => ({ ...s, __create: true }))
    try {
      const body = {
        kind: createForm.kind,
        label: createForm.label.trim() || undefined,
        enabled: createForm.enabled,
        event_types: createForm.event_types,
        config: createForm.kind === 'telegram'
          ? { token: createForm.token.trim(), chat_id: createForm.chat_id.trim() }
          : { url: createForm.url.trim() },
      }
      if (createForm.id.trim()) body.id = createForm.id.trim()
      await adminApi.postJson('/webhooks/destinations', body)
      setCreateForm(EMPTY_CREATE)
      setShowCreate(false)
      await loadDestinations()
      toast('Destination created', true)
    } catch (e) {
      toast(`Create failed: ${e.message}`, false)
    } finally {
      setSaving(s => ({ ...s, __create: false }))
    }
  }

  async function confirmDelete(id) {
    try {
      await adminApi.delJson(`/webhooks/destinations/${id}`, { confirm_text: 'delete' })
      setDeleteTarget(null)
      await loadDestinations()
      toast('Destination deleted', true)
    } catch (e) {
      toast(`Delete failed: ${e.message}`, false)
    }
  }

  function openEventEditor(dest) {
    setEventDraft(d => ({ ...d, [dest.id]: [...dest.event_types] }))
    setExpanded(e => ({ ...e, [dest.id]: true }))
  }

  function openConfigEditor(dest) {
    setConfigDraft(d => ({
      ...d,
      [dest.id]: {
        url: '',
        token: '',
        chat_id: dest.config?.chat_id || '',
      },
    }))
    setExpanded(e => ({ ...e, [`cfg-${dest.id}`]: true }))
  }

  const stackTerms = envStack || userStack

  return (
    <div>
      <h1 className="admin-page-title">
        Webhooks
        <HelpTip text="Destinations receive alert events (KEV, watchlist, backups, etc.). Env bootstrap rows come from API keys & config; add more destinations here. Secrets are masked after save — re-enter to change." />
      </h1>
      <p className="admin-page-subtitle">
        Manage delivery endpoints, event subscriptions, and test sends. Legacy Discord/Telegram/generic env vars on API keys &amp; config still seed the default destinations.
      </p>

      <div className="admin-action-bar">
        <button
          className="admin-btn admin-btn-primary"
          style={{ fontSize: '0.8125rem' }}
          onClick={() => setShowCreate(v => !v)}
        >
          {showCreate ? 'Cancel' : 'Add destination'}
        </button>
        <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.8125rem' }} onClick={loadDestinations}>
          Refresh
        </button>
      </div>

      {showCreate && (
        <div className="admin-card">
          <div className="admin-card-title">New destination</div>
          <div className="admin-filter-bar" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.75rem', color: 'var(--text2)' }}>
              Kind
              <select
                className="admin-select"
                style={{ marginLeft: '0.35rem' }}
                value={createForm.kind}
                onChange={e => setCreateForm(f => ({ ...f, kind: e.target.value }))}
              >
                {KIND_OPTIONS.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            </label>
            <label style={{ fontSize: '0.75rem', color: 'var(--text2)' }}>
              Id (optional)
              <input
                className="admin-input"
                style={{ marginLeft: '0.35rem', width: '10rem' }}
                placeholder="discord-ops"
                value={createForm.id}
                onChange={e => setCreateForm(f => ({ ...f, id: e.target.value }))}
              />
            </label>
            <label style={{ fontSize: '0.75rem', color: 'var(--text2)' }}>
              Label
              <input
                className="admin-input"
                style={{ marginLeft: '0.35rem', width: '12rem' }}
                value={createForm.label}
                onChange={e => setCreateForm(f => ({ ...f, label: e.target.value }))}
              />
            </label>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            {createForm.kind === 'telegram' ? (
              <div className="admin-filter-bar" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
                <input className="admin-input" type="password" placeholder="Bot token" value={createForm.token} onChange={e => setCreateForm(f => ({ ...f, token: e.target.value }))} />
                <input className="admin-input" placeholder="Chat ID" value={createForm.chat_id} onChange={e => setCreateForm(f => ({ ...f, chat_id: e.target.value }))} />
              </div>
            ) : (
              <input
                className="admin-input"
                style={{ width: '100%', maxWidth: '32rem' }}
                placeholder="https://… webhook URL"
                value={createForm.url}
                onChange={e => setCreateForm(f => ({ ...f, url: e.target.value }))}
              />
            )}
          </div>
          <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text2)' }}>Subscribed events</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem 1rem', marginTop: '0.35rem' }}>
            {EVENT_OPTIONS.map(opt => (
              <label key={opt.id} style={{ fontSize: '0.75rem', display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={createForm.event_types.includes(opt.id)}
                  onChange={e => {
                    setCreateForm(f => ({
                      ...f,
                      event_types: e.target.checked
                        ? [...f.event_types, opt.id]
                        : f.event_types.filter(x => x !== opt.id),
                    }))
                  }}
                />
                {opt.label}
              </label>
            ))}
          </div>
          <div style={{ marginTop: '0.75rem' }}>
            <button
              className="admin-btn admin-btn-primary"
              style={{ fontSize: '0.8125rem' }}
              disabled={saving.__create}
              onClick={createDestination}
            >
              {saving.__create ? 'Creating…' : 'Create destination'}
            </button>
          </div>
        </div>
      )}

      <AsyncSection data={destinations} error={loadError} onRetry={loadDestinations} emptyMessage="No webhook destinations">
        {(rows) => (
          <div className="admin-card">
            <div className="admin-card-title">Destinations ({rows.length})</div>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>KIND</th>
                  <th>SOURCE</th>
                  <th>ENABLED</th>
                  <th>CONFIG</th>
                  <th>EVENTS</th>
                  <th>TEST</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map(dest => (
                  <Fragment key={dest.id}>
                    <tr>
                      <td>
                        <div style={{ fontWeight: 600 }}>{dest.label || dest.id}</div>
                        <div className="mono" style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>{dest.id}</div>
                      </td>
                      <td style={{ textTransform: 'capitalize' }}>{dest.kind}</td>
                      <td>{sourceBadge(dest.source)}</td>
                      <td>
                        <ToggleSwitch
                          on={!!dest.enabled}
                          disabled={!!saving[dest.id]}
                          onChange={v => toggleEnabled(dest, v)}
                        />
                      </td>
                      <td className="mono" style={{ fontSize: '0.65rem', maxWidth: '14rem' }} title={configSummary(dest)}>
                        {configSummary(dest)}
                      </td>
                      <td style={{ fontSize: '0.7rem' }}>
                        {dest.event_types?.length || 0} subscribed
                        <button
                          className="admin-btn admin-btn-ghost"
                          style={{ fontSize: '0.65rem', padding: '0.1rem 0.3rem', marginLeft: '0.35rem' }}
                          onClick={() => openEventEditor(dest)}
                        >
                          Edit
                        </button>
                      </td>
                      <td>
                        {results[dest.id] && (
                          <span className={`badge ${results[dest.id].ok ? 'badge-ok' : 'badge-error'}`} style={{ fontSize: '0.6rem', marginRight: '0.35rem' }}>
                            {results[dest.id].ok ? 'ok' : 'fail'}
                          </span>
                        )}
                        <button
                          className="admin-btn admin-btn-ghost"
                          style={{ fontSize: '0.75rem', padding: '0.15rem 0.45rem' }}
                          onClick={() => testDestination(dest.id)}
                          disabled={testing[dest.id]}
                        >
                          {testing[dest.id] ? '…' : 'Test'}
                        </button>
                      </td>
                      <td>
                        {dest.source === 'db' && (
                          <button
                            className="admin-btn admin-btn-ghost"
                            style={{ fontSize: '0.7rem', color: 'var(--red)' }}
                            onClick={() => setDeleteTarget(dest.id)}
                          >
                            Delete
                          </button>
                        )}
                        {dest.source === 'db' && (
                          <button
                            className="admin-btn admin-btn-ghost"
                            style={{ fontSize: '0.65rem', padding: '0.1rem 0.3rem', marginLeft: '0.25rem' }}
                            onClick={() => openConfigEditor(dest)}
                          >
                            Config
                          </button>
                        )}
                      </td>
                    </tr>
                    {expanded[dest.id] && eventDraft[dest.id] && (
                      <tr key={`${dest.id}-events`}>
                        <td colSpan={8} style={{ background: 'var(--surface2)' }}>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem 1rem', padding: '0.5rem 0' }}>
                            {EVENT_OPTIONS.map(opt => (
                              <label key={opt.id} style={{ fontSize: '0.75rem', display: 'flex', gap: '0.35rem' }}>
                                <input
                                  type="checkbox"
                                  checked={eventDraft[dest.id].includes(opt.id)}
                                  onChange={e => {
                                    setEventDraft(d => ({
                                      ...d,
                                      [dest.id]: e.target.checked
                                        ? [...d[dest.id], opt.id]
                                        : d[dest.id].filter(x => x !== opt.id),
                                    }))
                                  }}
                                />
                                {opt.label}
                              </label>
                            ))}
                          </div>
                          <button className="admin-btn admin-btn-primary" style={{ fontSize: '0.75rem', marginTop: '0.35rem' }} disabled={saving[dest.id]} onClick={() => saveEventTypes(dest)}>
                            Save events
                          </button>
                        </td>
                      </tr>
                    )}
                    {expanded[`cfg-${dest.id}`] && configDraft[dest.id] && dest.source === 'db' && (
                      <tr key={`${dest.id}-cfg`}>
                        <td colSpan={8} style={{ background: 'var(--surface2)' }}>
                          {dest.kind === 'telegram' ? (
                            <div className="admin-filter-bar" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
                              <input className="admin-input" type="password" placeholder="New bot token" value={configDraft[dest.id].token} onChange={e => setConfigDraft(d => ({ ...d, [dest.id]: { ...d[dest.id], token: e.target.value } }))} />
                              <input className="admin-input" placeholder="Chat ID" value={configDraft[dest.id].chat_id} onChange={e => setConfigDraft(d => ({ ...d, [dest.id]: { ...d[dest.id], chat_id: e.target.value } }))} />
                            </div>
                          ) : (
                            <input className="admin-input" style={{ width: '100%', maxWidth: '32rem' }} type="password" placeholder="New HTTPS webhook URL" value={configDraft[dest.id].url} onChange={e => setConfigDraft(d => ({ ...d, [dest.id]: { ...d[dest.id], url: e.target.value } }))} />
                          )}
                          <button className="admin-btn admin-btn-primary" style={{ fontSize: '0.75rem', marginTop: '0.35rem' }} disabled={saving[dest.id]} onClick={() => saveConfig(dest)}>
                            Save config
                          </button>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </AsyncSection>

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
          {envStack ? (
            <>Using operator override <code className="mono">BRIEFR_STACK_TERMS</code> from API keys &amp; config.</>
          ) : (
            <>Set stack in the Feed tab, or optional <code className="mono">BRIEFR_STACK_TERMS</code> on API keys &amp; config.</>
          )}
        </div>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Dedupe log (legacy)</div>
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

      {deleteTarget && (
        <ConfirmModal
          actionId="webhook.destination.delete"
          title={`Delete destination ${deleteTarget}?`}
          onConfirm={() => confirmDelete(deleteTarget)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  )
}
