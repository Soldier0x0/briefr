import { useState, useEffect, useCallback, useMemo } from 'react'
import { adminApi, fetchUserStack } from '../../api.js'
import { fmtIso } from './formatters.js'
import AsyncSection from './shared/AsyncSection.jsx'
import ConfirmModal from './shared/ConfirmModal.jsx'
import HelpTip from './shared/HelpTip.jsx'
import AdminDataGrid from './shared/AdminDataGrid.jsx'
import WebhookDestinationCard from './WebhookDestinationCard.jsx'
import './WebhooksPage.css'

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
  const [health, setHealth] = useState(null)
  const [healthError, setHealthError] = useState(null)
  const [deliveryLog, setDeliveryLog] = useState(null)
  const [deliveryLogError, setDeliveryLogError] = useState(null)
  const [deliveryLogOffset, setDeliveryLogOffset] = useState(0)
  const [deliveryLogFilter, setDeliveryLogFilter] = useState('')
  const [dedupeLog, setDedupeLog] = useState(null)
  const [dedupeLogError, setDedupeLogError] = useState(null)
  const [dedupeLogOffset, setDedupeLogOffset] = useState(0)
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

  const loadHealth = useCallback(async () => {
    try {
      const { data } = await adminApi.getJson('/webhooks/health')
      setHealth(data.destinations || [])
      setHealthError(null)
    } catch (e) {
      setHealthError(e)
      setHealth(null)
    }
  }, [])

  useEffect(() => {
    loadDestinations()
    loadHealth()
    adminApi.get('/config').then(r => r.json()).then(c => {
      setEnvStack((c?.app?.BRIEFR_STACK_TERMS || '').trim())
    }).catch(() => {})
    fetchUserStack().then(d => setUserStack(d?.stack_terms || '')).catch(() => {})
  }, [loadDestinations, loadHealth])

  const loadDeliveryLog = useCallback(async (offset = 0, destinationId = deliveryLogFilter) => {
    try {
      const params = new URLSearchParams({ limit: String(logLimit), offset: String(offset) })
      if (destinationId) params.set('destination_id', destinationId)
      const res = await adminApi.get(`/webhooks/delivery-log?${params}`)
      setDeliveryLog(await res.json())
      setDeliveryLogOffset(offset)
      setDeliveryLogError(null)
    } catch (e) {
      setDeliveryLogError(e)
      setDeliveryLog(null)
    }
  }, [deliveryLogFilter])

  const loadDedupeLog = useCallback(async (offset = 0) => {
    try {
      const res = await adminApi.get(`/webhooks/log?limit=${logLimit}&offset=${offset}`)
      setDedupeLog(await res.json())
      setDedupeLogOffset(offset)
      setDedupeLogError(null)
    } catch (e) {
      setDedupeLogError(e)
      setDedupeLog(null)
    }
  }, [])

  useEffect(() => { loadDeliveryLog(0, deliveryLogFilter) }, [deliveryLogFilter, loadDeliveryLog])
  useEffect(() => { loadDedupeLog(0) }, [loadDedupeLog])

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
      try {
        await loadHealth()
        await loadDeliveryLog(deliveryLogOffset, deliveryLogFilter)
      } catch {
        /* refresh failure must not mask test result toast */
      }
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
      await loadHealth()
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
      await loadHealth()
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
      await loadHealth()
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

  const healthById = useMemo(() => {
    const map = {}
    for (const row of health || []) map[row.id] = row
    return map
  }, [health])

  const deliveryColumns = useMemo(() => [
    {
      id: 'attempted_at',
      label: 'Time',
      defaultVisible: true,
      render: (row) => <span className="mono">{fmtIso(row.attempted_at)}</span>,
    },
    {
      id: 'destination_id',
      label: 'Destination',
      defaultVisible: true,
      render: (row) => <span className="mono">{row.destination_id}</span>,
    },
    {
      id: 'event_type',
      label: 'Event',
      defaultVisible: true,
      render: (row) => <span className="badge badge-muted">{row.event_type}</span>,
    },
    {
      id: 'status',
      label: 'Status',
      defaultVisible: true,
      render: (row) => (
        <span className={`badge ${row.status === 'ok' ? 'badge-ok' : 'badge-error'}`}>
          {row.status}
        </span>
      ),
    },
    {
      id: 'dedupe_key',
      label: 'Dedupe key',
      defaultVisible: true,
      render: (row) => (
        <span className="mono" style={{ fontSize: '0.7rem', color: 'var(--text3)' }}>
          {row.dedupe_key || '—'}
        </span>
      ),
    },
    {
      id: 'error',
      label: 'Error',
      defaultVisible: true,
      render: (row) => (
        <span style={{ fontSize: '0.7rem', color: row.error ? 'var(--amber)' : 'var(--text3)' }}>
          {row.error || '—'}
        </span>
      ),
    },
  ], [])

  const destinationFilterOptions = useMemo(() => {
    const ids = new Set((destinations || []).map(d => d.id))
    for (const row of health || []) ids.add(row.id)
    return Array.from(ids).sort()
  }, [destinations, health])

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
        <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.8125rem' }} onClick={() => { loadDestinations(); loadHealth() }}>
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

      <AsyncSection data={destinations} error={loadError} onRetry={() => { loadDestinations(); loadHealth() }} emptyMessage="No webhook destinations">
        {(rows) => (
          <div className="admin-card">
            <div className="admin-card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              Destinations ({rows.length})
              <HelpTip text="Delivery health is derived from webhook_delivery_log — last success, last failure, and 24h attempt counts. Test send writes a health event immediately." />
            </div>
            {healthError && (
              <p style={{ fontSize: '0.75rem', color: 'var(--amber)', margin: '0 0 0.65rem' }}>
                Health summary unavailable: {healthError.message || String(healthError)}
              </p>
            )}
            <div className="webhook-dest-grid">
              {rows.map(dest => (
                <div key={dest.id}>
                  <WebhookDestinationCard
                    dest={dest}
                    health={healthById[dest.id]}
                    testResult={results[dest.id]}
                    testing={!!testing[dest.id]}
                    saving={!!saving[dest.id]}
                    onToggleEnabled={(v) => toggleEnabled(dest, v)}
                    onTest={() => testDestination(dest.id)}
                    onEditEvents={() => openEventEditor(dest)}
                    onEditConfig={() => openConfigEditor(dest)}
                    onDelete={() => setDeleteTarget(dest.id)}
                  />
                  {expanded[dest.id] && eventDraft[dest.id] && (
                    <div className="webhook-dest-expand">
                      <div style={{ fontSize: '0.7rem', color: 'var(--text3)', marginBottom: '0.35rem' }}>Subscribed events</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem 1rem' }}>
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
                      <button className="admin-btn admin-btn-primary" style={{ fontSize: '0.75rem', marginTop: '0.5rem' }} disabled={saving[dest.id]} onClick={() => saveEventTypes(dest)}>
                        Save events
                      </button>
                    </div>
                  )}
                  {expanded[`cfg-${dest.id}`] && configDraft[dest.id] && dest.source === 'db' && (
                    <div className="webhook-dest-expand">
                      {dest.kind === 'telegram' ? (
                        <div className="admin-filter-bar" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
                          <input className="admin-input" type="password" placeholder="New bot token" value={configDraft[dest.id].token} onChange={e => setConfigDraft(d => ({ ...d, [dest.id]: { ...d[dest.id], token: e.target.value } }))} />
                          <input className="admin-input" placeholder="Chat ID" value={configDraft[dest.id].chat_id} onChange={e => setConfigDraft(d => ({ ...d, [dest.id]: { ...d[dest.id], chat_id: e.target.value } }))} />
                        </div>
                      ) : (
                        <input className="admin-input" style={{ width: '100%' }} type="password" placeholder="New HTTPS webhook URL" value={configDraft[dest.id].url} onChange={e => setConfigDraft(d => ({ ...d, [dest.id]: { ...d[dest.id], url: e.target.value } }))} />
                      )}
                      <button className="admin-btn admin-btn-primary" style={{ fontSize: '0.75rem', marginTop: '0.5rem' }} disabled={saving[dest.id]} onClick={() => saveConfig(dest)}>
                        Save config
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
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
        <div className="admin-card-title">Delivery log</div>
        <div className="webhook-delivery-toolbar">
          <label style={{ fontSize: '0.75rem', color: 'var(--text2)' }}>
            Destination
            <select
              className="admin-select"
              style={{ marginLeft: '0.35rem' }}
              value={deliveryLogFilter}
              onChange={(e) => setDeliveryLogFilter(e.target.value)}
            >
              <option value="">All destinations</option>
              {destinationFilterOptions.map((id) => (
                <option key={id} value={id}>{id}</option>
              ))}
            </select>
          </label>
          <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={() => loadDeliveryLog(deliveryLogOffset, deliveryLogFilter)}>
            Refresh
          </button>
        </div>
        <AsyncSection
          data={deliveryLogError ? null : (deliveryLog?.rows ?? null)}
          error={deliveryLogError}
          loading={deliveryLog === null && !deliveryLogError}
          onRetry={() => loadDeliveryLog(deliveryLogOffset, deliveryLogFilter)}
          emptyMessage="No delivery attempts logged yet"
        >
          {(deliveryRows) => (
            <AdminDataGrid
              gridId="webhook-delivery-log"
              columns={deliveryColumns}
              rows={deliveryRows}
              rowKey={(row) => row.id}
              emptyMessage="No delivery rows"
            />
          )}
        </AsyncSection>
        {deliveryLog && (
          <div className="admin-pagination">
            <button className="admin-btn admin-btn-ghost" disabled={deliveryLogOffset === 0} onClick={() => loadDeliveryLog(Math.max(0, deliveryLogOffset - logLimit), deliveryLogFilter)}>← Prev</button>
            <span style={{ color: 'var(--text3)', fontSize: '0.8125rem' }}>
              {deliveryLog.total === 0 ? '0 rows' : `${deliveryLogOffset + 1}–${Math.min(deliveryLogOffset + logLimit, deliveryLog.total)} of ${deliveryLog.total}`}
            </span>
            <button className="admin-btn admin-btn-ghost" disabled={deliveryLogOffset + logLimit >= deliveryLog.total} onClick={() => loadDeliveryLog(deliveryLogOffset + logLimit, deliveryLogFilter)}>Next →</button>
          </div>
        )}
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Dedupe log (legacy)</div>
        <div className="admin-filter-bar">
          <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={() => loadDedupeLog(dedupeLogOffset)}>
            Refresh dedupe
          </button>
        </div>
        <AsyncSection
          data={dedupeLogError ? null : (dedupeLog?.rows ?? null)}
          error={dedupeLogError}
          loading={dedupeLog === null && !dedupeLogError}
          onRetry={() => loadDedupeLog(dedupeLogOffset)}
          emptyMessage="No webhook alerts logged yet"
        >
          {(rows) => (
            <table className="admin-table">
              <thead><tr><th>EVENT TYPE</th><th>TARGET</th><th>ALERTED AT</th></tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    <td><span className="badge badge-muted">{r.alert_type}</span></td>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{r.target}</td>
                    <td style={{ fontSize: '0.75rem' }}>{fmtIso(r.alerted_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </AsyncSection>
        {dedupeLog && (
          <div className="admin-pagination">
            <button className="admin-btn admin-btn-ghost" disabled={dedupeLogOffset === 0} onClick={() => loadDedupeLog(Math.max(0, dedupeLogOffset - logLimit))}>← Prev</button>
            <span style={{ color: 'var(--text3)', fontSize: '0.8125rem' }}>
              {dedupeLog.total === 0 ? '0 rows' : `${dedupeLogOffset + 1}–${Math.min(dedupeLogOffset + logLimit, dedupeLog.total)} of ${dedupeLog.total}`}
            </span>
            <button className="admin-btn admin-btn-ghost" disabled={dedupeLogOffset + logLimit >= dedupeLog.total} onClick={() => loadDedupeLog(dedupeLogOffset + logLimit)}>Next →</button>
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
