import { useState, useEffect, useCallback, useRef } from 'react'
import { adminApi, getAdminKey, setAdminKey, clearAdminKey } from '../api.js'
import AdminPage_KeyModal from './AdminPage_KeyModal.jsx'
import './AdminPage.css'

// ── Helpers ────────────────────────────────────────────────────────────────

function fmtAge(seconds) {
  if (seconds === null || seconds === undefined) return '—'
  const s = Math.round(seconds)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return `${Math.round(s / 86400)}d ago`
}

function fmtBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let val = bytes
  while (val >= 1024 && i < units.length - 1) { val /= 1024; i++ }
  return `${val.toFixed(1)} ${units[i]}`
}

function fmtDur(sec) {
  if (sec === null || sec === undefined) return '—'
  if (sec < 60) return `${sec.toFixed(1)}s`
  return `${(sec / 60).toFixed(1)}m`
}

function fmtIso(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString() } catch { return iso }
}

const SOURCE_DISPLAY = {
  nvd: 'NVD API', kev: 'CISA KEV', epss: 'FIRST EPSS',
  mitre_attack: 'MITRE ATT&CK', mitre_atlas: 'MITRE ATLAS',
  otx: 'OTX', cvelistv5: 'CVE List V5', vulnrichment: 'CISA Vulnrichment',
  embeddings: 'CVE Embeddings', llm: 'Groq Product Extraction',
  exploitdb: 'ExploitDB', metasploit: 'Metasploit',
  nuclei: 'Nuclei Templates', poc_github: 'PoC-in-GitHub',
  'webhook.discord': 'Discord Webhook', 'webhook.telegram': 'Telegram Webhook',
}

function sourceLabel(key) { return SOURCE_DISPLAY[key] || key }

// ── Toast ──────────────────────────────────────────────────────────────────

function useToast() {
  const [toasts, setToasts] = useState([])
  const show = useCallback((msg, ok = true) => {
    const id = Date.now()
    setToasts(t => [...t, { id, msg, ok }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3500)
  }, [])
  return { toasts, show }
}

function ToastArea({ toasts }) {
  return (
    <div className="admin-toast-area">
      {toasts.map(t => (
        <div key={t.id} className={`admin-toast ${t.ok ? 'admin-toast-ok' : 'admin-toast-error'}`}>
          {t.msg}
        </div>
      ))}
    </div>
  )
}

// ── Status bar ─────────────────────────────────────────────────────────────

function StatusBar({ system, onRunIngest, onRestart, refreshInProgress }) {
  const [confirmRestart, setConfirmRestart] = useState(false)

  function handleRestartClick() {
    if (!confirmRestart) { setConfirmRestart(true); return }
    setConfirmRestart(false)
    onRestart()
  }

  const nvdInterval = 1
  const nvdThreshold = nvdInterval * 2 * 3600
  const nvdAge = system?.last_nvd_sync_age_seconds
  const backupAge = system?.last_backup_age_seconds
  const backupThreshold = system?.backup_threshold_seconds || 43200
  const openCircuits = system?.open_circuit_count || 0
  const integrityOk = system?.db_integrity?.ok !== false
  const discordOpen = system?.feeds?.sources?.['webhook.discord']?.circuit_open
  const telegramOpen = system?.feeds?.sources?.['webhook.telegram']?.circuit_open
  const commit = system?.version?.commit

  return (
    <div className="admin-statusbar">
      <span className="sb-item">
        <span className="sb-label">CVEs</span>
        <span className="sb-value">{system?.cve_count ?? '…'}</span>
      </span>
      <div className="sb-sep" />
      <span className="sb-item">
        <span className="sb-label">NVD sync</span>
        <span className={`sb-value ${nvdAge !== null && nvdAge > nvdThreshold ? 'sb-warn' : ''}`}>
          {nvdAge !== null && nvdAge !== undefined ? fmtAge(nvdAge) : '—'}
        </span>
      </span>
      {backupAge !== null && backupAge !== undefined && (
        <>
          <div className="sb-sep" />
          <span className="sb-item">
            <span className="sb-label">Backup</span>
            <span className={`sb-value ${backupAge > backupThreshold ? 'sb-warn' : ''}`}>
              {fmtAge(backupAge)}
            </span>
          </span>
        </>
      )}
      <div className="sb-sep" />
      <span className="sb-item">
        <span className="sb-label">Circuits</span>
        <span className={`sb-value ${openCircuits > 0 ? 'sb-warn' : ''}`}>{openCircuits} open</span>
      </span>
      <div className="sb-sep" />
      <span className="sb-item">
        <span className={`dot ${integrityOk ? 'dot-ok' : 'dot-error'}`} />
        <span className="sb-label">DB {integrityOk ? 'ok' : 'degraded'}</span>
      </span>
      <div className="sb-sep" />
      <span className="sb-item">
        <span className={`pill ${discordOpen ? 'pill-open' : 'pill-closed'}`}>Discord</span>
      </span>
      <span className="sb-item">
        <span className={`pill ${telegramOpen ? 'pill-open' : 'pill-closed'}`}>Telegram</span>
      </span>
      {commit && (
        <>
          <div className="sb-sep" />
          <span className="sb-item">
            <span className="sb-label">v</span>
            <span className="sb-value mono">{commit.slice(0, 7) || 'dev'}</span>
          </span>
        </>
      )}
      <div className="sb-actions">
        <button
          className="admin-btn admin-btn-warn"
          onClick={onRunIngest}
          disabled={refreshInProgress}
          style={{ fontSize: '0.75rem' }}
        >
          {refreshInProgress ? <><span className="admin-spinner" /> Running…</> : 'Run full ingest'}
        </button>
        <button
          className={`admin-btn ${confirmRestart ? 'admin-btn-danger' : 'admin-btn-ghost'}`}
          onClick={handleRestartClick}
          style={{ fontSize: '0.75rem' }}
          onBlur={() => setTimeout(() => setConfirmRestart(false), 300)}
        >
          {confirmRestart ? 'Confirm restart?' : 'Restart backend'}
        </button>
      </div>
    </div>
  )
}

// ── Sidebar nav ────────────────────────────────────────────────────────────

const NAV = [
  { section: 'OVERVIEW', items: [{ id: 'overview', label: 'System health' }] },
  { section: 'DATA', items: [
    { id: 'backups', label: 'Backups' },
    { id: 'storage', label: 'Storage' },
    { id: 'watchlist', label: 'Watchlist & cache' },
  ]},
  { section: 'CONFIG', items: [
    { id: 'apikeys', label: 'API keys & config' },
    { id: 'scheduler', label: 'Scheduler config' },
    { id: 'webhooks', label: 'Webhooks' },
    { id: 'security', label: 'Security', badgeKey: 'failed_auth_last_24h' },
  ]},
  { section: 'FEEDS', items: [
    { id: 'feedhealth', label: 'Feed health', badgeKey: 'open_circuit_count' },
    { id: 'ingestlog', label: 'Ingest log' },
  ]},
  { section: 'AUDIT', items: [
    { id: 'auditlog', label: 'Audit log' },
  ]},
]

function Sidebar({ activePage, setPage, system }) {
  const openCircuits = system?.open_circuit_count || 0
  const failedAuth = system?.failed_auth_last_24h || 0

  return (
    <nav className="admin-sidebar">
      {NAV.map(section => (
        <div key={section.section}>
          <div className="nav-section-label">{section.section}</div>
          {section.items.map(item => {
            let badge = 0
            if (item.badgeKey === 'open_circuit_count') badge = openCircuits
            if (item.badgeKey === 'failed_auth_last_24h') badge = failedAuth
            return (
              <div
                key={item.id}
                className={`nav-item ${activePage === item.id ? 'active' : ''}`}
                onClick={() => setPage(item.id)}
              >
                {item.label}
                {badge > 0 && <span className="nav-badge">{badge}</span>}
              </div>
            )
          })}
        </div>
      ))}
    </nav>
  )
}

// ── Page: Overview ─────────────────────────────────────────────────────────

function PageOverview({ system }) {
  if (!system) return <div style={{ color: 'var(--text-muted)' }}>Loading…</div>
  const { db_integrity, epss_backfill_done, refresh_in_progress, scheduler_jobs } = system

  return (
    <div>
      <h1 className="admin-page-title">System health</h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        {[
          { label: 'CVE Count', value: system.cve_count?.toLocaleString() },
          { label: 'NVD Sync Age', value: fmtAge(system.last_nvd_sync_age_seconds) },
          { label: 'Last Backup', value: fmtAge(system.last_backup_age_seconds) },
          { label: 'DB Integrity', value: db_integrity?.ok ? '✓ OK' : '✗ ' + db_integrity?.message, warn: !db_integrity?.ok },
          { label: 'EPSS Backfill', value: epss_backfill_done ? 'Done' : 'Pending' },
          { label: 'Ingest Active', value: refresh_in_progress ? 'Yes' : 'No', warn: refresh_in_progress },
        ].map(c => (
          <div key={c.label} className="admin-card" style={{ marginBottom: 0 }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>{c.label}</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: c.warn ? 'var(--color-warn)' : 'var(--text-primary)' }}>{c.value ?? '—'}</div>
          </div>
        ))}
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Scheduler jobs</div>
        <table className="admin-table">
          <thead>
            <tr>
              <th>Job</th><th>Next run</th><th>Paused</th>
              <th>Last run</th><th>Duration</th><th>Records</th><th>Error</th>
            </tr>
          </thead>
          <tbody>
            {(scheduler_jobs || []).map(job => (
              <tr key={job.id}>
                <td className="mono" style={{ fontSize: '0.75rem' }}>{job.id}</td>
                <td>{job.paused ? <span className="badge badge-warn">paused</span> : fmtIso(job.next_run_time)}</td>
                <td>{job.paused ? '✓' : ''}</td>
                <td>{fmtIso(job.last_run_utc)}</td>
                <td>{fmtDur(job.last_run_duration_seconds)}</td>
                <td>{job.last_run_records_upserted ?? '—'}</td>
                <td>{job.last_run_had_error === true ? <span className="badge badge-error">yes</span> : job.last_run_had_error === false ? '' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Page: Backups ──────────────────────────────────────────────────────────

function PageBackups({ toast }) {
  const [backups, setBackups] = useState(null)
  const [loading, setLoading] = useState(false)
  const fileInputRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const res = await adminApi.get('/backups')
      setBackups(await res.json())
    } catch { setBackups([]) }
  }, [])

  useEffect(() => { load() }, [load])

  async function runBackup() {
    setLoading(true)
    try {
      const res = await adminApi.post('/backups/run', {})
      const data = await res.json()
      toast(data.ok ? `Backup created: ${data.filename}` : 'Backup failed', data.ok)
      if (data.ok) load()
    } catch (e) {
      toast(e.status === 409 ? 'Backup already in progress' : String(e.message), false)
    }
    setLoading(false)
  }

  async function verifyBackup(filename) {
    try {
      const res = await adminApi.post(`/backups/verify/${encodeURIComponent(filename)}`, {})
      const data = await res.json()
      toast(data.ok ? `Verified: ${data.details}` : `Verify failed: ${data.details}`, data.ok)
    } catch (e) { toast(String(e.message), false) }
  }

  async function uploadBackup(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await adminApi.postForm('/backups/upload', formData)
      const data = await res.json()
      toast(data.ok ? `Uploaded: ${data.filename}` : 'Upload failed', data.ok)
      if (data.ok) load()
    } catch (e) { toast(String(e.message), false) }
    e.target.value = ''
  }

  return (
    <div>
      <h1 className="admin-page-title">Backups</h1>
      <div className="admin-action-bar">
        <button className="admin-btn admin-btn-primary" onClick={runBackup} disabled={loading}>
          {loading ? <><span className="admin-spinner" /> Running…</> : 'Run backup now'}
        </button>
        <button className="admin-btn admin-btn-ghost" onClick={() => fileInputRef.current?.click()}>
          Upload backup
        </button>
        <input ref={fileInputRef} type="file" accept=".tar.gz,.age" style={{ display: 'none' }} onChange={uploadBackup} />
      </div>
      <div className="admin-card">
        <table className="admin-table">
          <thead>
            <tr><th>Filename</th><th>Created</th><th>Size</th><th>Encrypted</th><th>Integrity</th><th>Reason</th><th></th></tr>
          </thead>
          <tbody>
            {backups === null && (
              <tr><td colSpan={7} style={{ color: 'var(--text-muted)' }}>Loading…</td></tr>
            )}
            {backups?.length === 0 && (
              <tr><td colSpan={7} style={{ color: 'var(--text-muted)' }}>No backups found</td></tr>
            )}
            {backups?.map(b => (
              <tr key={b.filename}>
                <td className="mono" style={{ fontSize: '0.75rem' }}>{b.filename}</td>
                <td>{fmtIso(b.created_at)}</td>
                <td>{fmtBytes(b.size_bytes)}</td>
                <td>{b.encrypted ? <span className="badge badge-info">encrypted</span> : ''}</td>
                <td>
                  <span className={`badge ${b.integrity === 'ok' ? 'badge-ok' : 'badge-warn'}`}>{b.integrity}</span>
                </td>
                <td>{b.reason || '—'}</td>
                <td>
                  <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                    onClick={() => verifyBackup(b.filename)}>Verify</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Page: Storage ──────────────────────────────────────────────────────────

function PageStorage({ toast }) {
  const [storage, setStorage] = useState(null)
  const [purgeTarget, setPurgeTarget] = useState('ioc_cache')
  const [purgeConfirm, setPurgeConfirm] = useState('')

  const load = useCallback(async () => {
    try {
      const res = await adminApi.get('/storage')
      setStorage(await res.json())
    } catch { }
  }, [])

  useEffect(() => { load() }, [load])

  async function doPurge() {
    try {
      const res = await adminApi.post('/storage/purge', { target: purgeTarget, confirm: purgeConfirm })
      const data = await res.json()
      toast(data.ok ? `Purged ${data.rows_deleted} rows from ${purgeTarget}` : 'Purge failed', data.ok)
      setPurgeConfirm('')
      load()
    } catch (e) { toast(String(e.message), false) }
  }

  const usedBytes = (storage?.disk_total_bytes || 0) - (storage?.disk_free_bytes || 0)
  const usedPct = storage ? Math.round(usedBytes / storage.disk_total_bytes * 100) : 0

  return (
    <div>
      <h1 className="admin-page-title">Storage</h1>
      {storage && (
        <div className="admin-card">
          <div className="admin-card-title">Disk usage</div>
          <div style={{ marginBottom: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            {fmtBytes(usedBytes)} / {fmtBytes(storage.disk_total_bytes)} ({usedPct}%)
          </div>
          <div className="disk-bar">
            <div className="disk-bar-fill" style={{ width: `${usedPct}%` }} />
          </div>
          <div style={{ marginTop: '0.4rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            DB: {storage.db_path} ({fmtBytes(storage.db_size_bytes)})
          </div>
        </div>
      )}
      <div className="admin-card">
        <div className="admin-card-title">Table row counts</div>
        <table className="admin-table">
          <thead><tr><th>Table</th><th style={{ textAlign: 'right' }}>Rows</th></tr></thead>
          <tbody>
            {Object.entries(storage?.tables || {}).map(([t, c]) => (
              <tr key={t}>
                <td className="mono" style={{ fontSize: '0.75rem' }}>{t}</td>
                <td style={{ textAlign: 'right' }}>{c === -1 ? 'n/a' : c.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="admin-card">
        <div className="admin-card-title">Purge data</div>
        <div className="admin-form-row">
          <label>Target</label>
          <select className="admin-select" value={purgeTarget} onChange={e => setPurgeTarget(e.target.value)}>
            <option value="ioc_cache">IOC Cache</option>
            <option value="feed_cache">Feed Cache</option>
            <option value="epss_history_old">EPSS History (&gt;90 days)</option>
            <option value="change_history_old">Change History (&gt;90 days)</option>
            <option value="rejected_cves">Rejected CVEs</option>
          </select>
        </div>
        <div className="admin-form-row">
          <label>Type <code>delete</code> to confirm</label>
          <input className="admin-input" value={purgeConfirm} onChange={e => setPurgeConfirm(e.target.value)} placeholder="delete" />
          <button className="admin-btn admin-btn-danger" onClick={doPurge} disabled={purgeConfirm !== 'delete'}>
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Page: Watchlist & cache ────────────────────────────────────────────────

function PageWatchlist({ toast }) {
  const [subtab, setSubtab] = useState('watchlist')
  const [watchlistState, setWatchlistState] = useState('all')
  const [watchlistRows, setWatchlistRows] = useState(null)
  const [iocRows, setIocRows] = useState(null)
  const [iocType, setIocType] = useState('')
  const [iocSearch, setIocSearch] = useState('')
  const [huntRows, setHuntRows] = useState(null)
  const [huntTechnique, setHuntTechnique] = useState('')

  async function loadWatchlist() {
    try {
      const res = await adminApi.get(`/watchlist?state=${watchlistState}&limit=200`)
      setWatchlistRows(await res.json())
    } catch { setWatchlistRows([]) }
  }

  async function loadIoc() {
    const params = new URLSearchParams({ limit: 100 })
    if (iocType) params.set('ioc_type', iocType)
    if (iocSearch) params.set('search', iocSearch)
    try {
      const res = await adminApi.get(`/ioc-cache?${params}`)
      setIocRows(await res.json())
    } catch { setIocRows([]) }
  }

  async function loadHunts() {
    const params = new URLSearchParams({ limit: 100 })
    if (huntTechnique) params.set('technique_id', huntTechnique)
    try {
      const res = await adminApi.get(`/hunt-packs?${params}`)
      setHuntRows(await res.json())
    } catch { setHuntRows([]) }
  }

  useEffect(() => { if (subtab === 'watchlist') loadWatchlist() }, [subtab, watchlistState])
  useEffect(() => { if (subtab === 'ioc') loadIoc() }, [subtab, iocType, iocSearch])
  useEffect(() => { if (subtab === 'hunt') loadHunts() }, [subtab, huntTechnique])

  async function removeWatchlist(cveId) {
    try {
      await adminApi.del(`/watchlist/${encodeURIComponent(cveId)}`)
      toast(`Removed ${cveId}`, true)
      loadWatchlist()
    } catch (e) { toast(String(e.message), false) }
  }

  async function clearSnoozes() {
    if (!window.confirm('Clear all legacy snooze entries?')) return
    try {
      const res = await adminApi.post('/watchlist/clear-snoozes', {})
      const data = await res.json()
      toast(`Cleared ${data.rows_deleted} snooze entries`, data.ok)
      loadWatchlist()
    } catch (e) { toast(String(e.message), false) }
  }

  async function deleteIoc(value) {
    try {
      await adminApi.del(`/ioc-cache/${encodeURIComponent(value)}`)
      toast('Deleted', true)
      loadIoc()
    } catch (e) { toast(String(e.message), false) }
  }

  async function deleteHunt(id) {
    try {
      await adminApi.del(`/hunt-packs/${id}`)
      toast('Deleted', true)
      loadHunts()
    } catch (e) { toast(String(e.message), false) }
  }

  return (
    <div>
      <h1 className="admin-page-title">Watchlist & cache</h1>
      <div className="admin-subtabs">
        {[['watchlist', 'Watchlist'], ['ioc', 'IOC Cache'], ['hunt', 'Hunt Packs']].map(([id, label]) => (
          <button key={id} className={`admin-subtab ${subtab === id ? 'active' : ''}`} onClick={() => setSubtab(id)}>{label}</button>
        ))}
      </div>

      {subtab === 'watchlist' && (
        <div>
          <div className="admin-action-bar">
            <button className="admin-btn admin-btn-danger" onClick={clearSnoozes}>Clear all legacy snoozes</button>
            {['all', 'pin', 'snooze'].map(s => (
              <button key={s} className={`admin-btn ${watchlistState === s ? 'admin-btn-primary' : 'admin-btn-ghost'}`}
                onClick={() => setWatchlistState(s)} style={{ textTransform: 'capitalize' }}>
                {s === 'snooze' ? 'Legacy snoozed' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
          <div className="admin-card">
            <table className="admin-table">
              <thead><tr><th>CVE ID</th><th>Severity</th><th>EPSS</th><th>State</th><th>Created</th><th></th></tr></thead>
              <tbody>
                {watchlistRows === null && <tr><td colSpan={6} style={{ color: 'var(--text-muted)' }}>Loading…</td></tr>}
                {watchlistRows?.length === 0 && <tr><td colSpan={6} style={{ color: 'var(--text-muted)' }}>None</td></tr>}
                {watchlistRows?.map(r => (
                  <tr key={r.cve_id}>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{r.cve_id}</td>
                    <td>{r.severity || '—'}</td>
                    <td>{r.epss_score != null ? (r.epss_score * 100).toFixed(1) + '%' : '—'}</td>
                    <td><span className={`badge ${r.state === 'pin' ? 'badge-info' : 'badge-warn'}`}>{r.state}</span></td>
                    <td>{fmtIso(r.created_at)}</td>
                    <td><button className="admin-btn admin-btn-danger" style={{ fontSize: '0.75rem', padding: '0.15rem 0.4rem' }}
                      onClick={() => removeWatchlist(r.cve_id)}>Remove</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {subtab === 'ioc' && (
        <div>
          <div className="admin-filter-bar">
            <select className="admin-select" value={iocType} onChange={e => setIocType(e.target.value)}>
              <option value="">All types</option>
              <option value="ip">IP</option>
              <option value="hash">Hash</option>
              <option value="domain">Domain</option>
            </select>
            <input className="admin-input" placeholder="Search…" value={iocSearch} onChange={e => setIocSearch(e.target.value)} />
          </div>
          <div className="admin-card">
            <table className="admin-table">
              <thead><tr><th>Value</th><th>Type</th><th>Cached at</th><th>Age</th><th></th></tr></thead>
              <tbody>
                {iocRows === null && <tr><td colSpan={5} style={{ color: 'var(--text-muted)' }}>Loading…</td></tr>}
                {iocRows?.length === 0 && <tr><td colSpan={5} style={{ color: 'var(--text-muted)' }}>None</td></tr>}
                {iocRows?.map((r, i) => (
                  <tr key={i}>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{r.value}</td>
                    <td>{r.ioc_type}</td>
                    <td>{fmtIso(r.cached_at)}</td>
                    <td>{fmtAge(r.age_seconds)}</td>
                    <td><button className="admin-btn admin-btn-danger" style={{ fontSize: '0.75rem', padding: '0.15rem 0.4rem' }}
                      onClick={() => deleteIoc(r.value)}>Delete</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {subtab === 'hunt' && (
        <div>
          <div className="admin-filter-bar">
            <input className="admin-input" placeholder="Filter by technique_id…" value={huntTechnique} onChange={e => setHuntTechnique(e.target.value)} />
          </div>
          <div className="admin-card">
            <table className="admin-table">
              <thead><tr><th>ID</th><th>Technique</th><th>CVE</th><th>Title</th><th>Priority</th><th>Created</th><th></th></tr></thead>
              <tbody>
                {huntRows === null && <tr><td colSpan={7} style={{ color: 'var(--text-muted)' }}>Loading…</td></tr>}
                {huntRows?.length === 0 && <tr><td colSpan={7} style={{ color: 'var(--text-muted)' }}>None</td></tr>}
                {huntRows?.map(r => (
                  <tr key={r.id}>
                    <td>{r.id}</td>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{r.technique_id}</td>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{r.cve_id}</td>
                    <td>{r.title}</td>
                    <td>{r.priority}</td>
                    <td>{fmtIso(r.created_at)}</td>
                    <td><button className="admin-btn admin-btn-danger" style={{ fontSize: '0.75rem', padding: '0.15rem 0.4rem' }}
                      onClick={() => deleteHunt(r.id)}>Delete</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Page: API keys & config ────────────────────────────────────────────────

function PageApiKeys({ toast }) {
  const [config, setConfig] = useState(null)
  const [editing, setEditing] = useState({})
  const [saving, setSaving] = useState({})

  useEffect(() => {
    adminApi.get('/config').then(r => r.json()).then(setConfig).catch(() => {})
  }, [])

  async function saveKey(key, value) {
    setSaving(s => ({ ...s, [key]: true }))
    try {
      const res = await adminApi.post('/config', { key, value })
      const data = await res.json()
      if (data.ok) {
        toast(`${key} updated${data.warning_restart_required ? ' (restart required)' : ''}`, true)
        setEditing(e => ({ ...e, [key]: undefined }))
        adminApi.get('/config').then(r => r.json()).then(setConfig).catch(() => {})
      } else {
        toast('Failed to update', false)
      }
    } catch (e) { toast(String(e.message), false) }
    setSaving(s => ({ ...s, [key]: false }))
  }

  function ConfigRow({ label, envKey, value, writable = true }) {
    const editVal = editing[envKey]
    const isEditing = editVal !== undefined
    return (
      <div className="admin-form-row" style={{ alignItems: 'flex-start', marginBottom: '0.5rem' }}>
        <label style={{ minWidth: 260, fontFamily: 'monospace', fontSize: '0.75rem', paddingTop: '0.35rem' }}>{envKey}</label>
        {!isEditing ? (
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
              {String(value)}
            </span>
            {writable && (
              <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem' }}
                onClick={() => setEditing(e => ({ ...e, [envKey]: String(value) }))}>
                Edit
              </button>
            )}
          </div>
        ) : (
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <input className="admin-input" style={{ minWidth: 220 }} value={editVal}
              onChange={e => setEditing(ed => ({ ...ed, [envKey]: e.target.value }))} />
            <button className="admin-btn admin-btn-primary" style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
              onClick={() => saveKey(envKey, editVal)} disabled={saving[envKey]}>
              {saving[envKey] ? 'Saving…' : 'Save'}
            </button>
            <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
              onClick={() => setEditing(e => ({ ...e, [envKey]: undefined }))}>Cancel</button>
          </div>
        )}
      </div>
    )
  }

  if (!config) return <div style={{ color: 'var(--text-muted)' }}>Loading…</div>

  return (
    <div>
      <h1 className="admin-page-title">API keys & config</h1>
      <div className="admin-callout admin-callout-amber">
        <strong>Note:</strong> <code>load_dotenv()</code> is called without <code>override=True</code>.
        Process environment variables (Cursor Secrets / systemd) win over <code>.env</code>.
        Restart the backend after making changes here.
      </div>
      <div className="admin-card">
        <div className="admin-card-title">API keys (read-only)</div>
        {Object.entries(config.api_keys || {}).map(([k, v]) => (
          <ConfigRow key={k} envKey={k} value={v} writable={false} />
        ))}
      </div>
      <div className="admin-card">
        <div className="admin-card-title">Scheduler</div>
        {Object.entries(config.scheduler || {}).map(([k, v]) => (
          <ConfigRow key={k} envKey={k} value={v} />
        ))}
      </div>
      <div className="admin-card">
        <div className="admin-card-title">Ingest</div>
        {Object.entries(config.ingest || {}).map(([k, v]) => (
          <ConfigRow key={k} envKey={k} value={v} writable={!['DB_PATH'].includes(k)} />
        ))}
      </div>
      <div className="admin-card">
        <div className="admin-card-title">ML</div>
        {Object.entries(config.ml || {}).map(([k, v]) => (
          <ConfigRow key={k} envKey={k} value={v} />
        ))}
      </div>
      <div className="admin-card">
        <div className="admin-card-title">Backup</div>
        {Object.entries(config.backup || {}).map(([k, v]) => (
          <ConfigRow key={k} envKey={k} value={v} writable={!['BACKUP_DIR', 'BACKUP_AGE_KEY_FILE'].includes(k)} />
        ))}
      </div>
      <div className="admin-card">
        <div className="admin-card-title">App</div>
        {Object.entries(config.app || {}).map(([k, v]) => (
          <ConfigRow key={k} envKey={k} value={Array.isArray(v) ? v.join(', ') : v} />
        ))}
      </div>
    </div>
  )
}

// ── Page: Scheduler config ─────────────────────────────────────────────────

function PageScheduler({ toast }) {
  const [jobs, setJobs] = useState(null)
  const [history, setHistory] = useState(null)

  async function loadJobs() {
    try {
      const res = await adminApi.get('/scheduler')
      setJobs(await res.json())
    } catch { }
  }

  async function loadHistory() {
    try {
      const res = await adminApi.get('/scheduler/history')
      setHistory(await res.json())
    } catch { }
  }

  useEffect(() => { loadJobs(); loadHistory() }, [])

  async function togglePause(job) {
    const action = job.paused ? 'resume' : 'pause'
    try {
      await adminApi.post(`/scheduler/${action}`, { job_id: job.id })
      toast(`Job ${action}d: ${job.id}`, true)
      loadJobs()
    } catch (e) { toast(String(e.message), false) }
  }

  return (
    <div>
      <h1 className="admin-page-title">Scheduler</h1>
      <div className="admin-card">
        <div className="admin-card-title">Jobs</div>
        <table className="admin-table">
          <thead>
            <tr>
              <th>Job ID</th><th>Name</th><th>Next run</th><th>Lock</th><th>Status</th>
              <th>Last run</th><th>Duration</th><th>Error</th><th></th>
            </tr>
          </thead>
          <tbody>
            {jobs === null && <tr><td colSpan={9} style={{ color: 'var(--text-muted)' }}>Loading…</td></tr>}
            {jobs?.map(job => (
              <tr key={job.id}>
                <td className="mono" style={{ fontSize: '0.7rem' }}>{job.id}</td>
                <td style={{ fontSize: '0.8rem' }}>{job.name}</td>
                <td style={{ fontSize: '0.75rem' }}>{job.paused ? '—' : fmtIso(job.next_run_time)}</td>
                <td>{job.lock_held ? <span className="badge badge-warn">held</span> : ''}</td>
                <td>{job.paused ? <span className="badge badge-warn">paused</span> : <span className="badge badge-ok">active</span>}</td>
                <td style={{ fontSize: '0.75rem' }}>{fmtIso(job.last_run_utc)}</td>
                <td>{fmtDur(job.last_run_duration_seconds)}</td>
                <td>{job.last_run_had_error === true ? <span className="badge badge-error">yes</span> : ''}</td>
                <td>
                  <button className={`admin-btn ${job.paused ? 'admin-btn-primary' : 'admin-btn-warn'}`}
                    style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem' }}
                    onClick={() => togglePause(job)}>
                    {job.paused ? 'Resume' : 'Pause'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="admin-card">
        <div className="admin-card-title">Run history</div>
        <table className="admin-table">
          <thead><tr><th>Job ID</th><th>Last run</th><th>Duration</th><th>Records</th><th>Error</th></tr></thead>
          <tbody>
            {history === null && <tr><td colSpan={5} style={{ color: 'var(--text-muted)' }}>Loading…</td></tr>}
            {history?.length === 0 && <tr><td colSpan={5} style={{ color: 'var(--text-muted)' }}>No history yet</td></tr>}
            {history?.map(h => (
              <tr key={h.job_id}>
                <td className="mono" style={{ fontSize: '0.75rem' }}>{h.job_id}</td>
                <td>{fmtIso(h.last_run_utc)}</td>
                <td>{fmtDur(h.duration_seconds)}</td>
                <td>{h.records_upserted ?? '—'}</td>
                <td>{h.had_error === true ? <span className="badge badge-error">yes</span> : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Page: Webhooks ─────────────────────────────────────────────────────────

function PageWebhooks({ toast }) {
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

  return (
    <div>
      <h1 className="admin-page-title">Webhooks</h1>
      {config && (
        <div className="admin-card">
          <div className="admin-card-title">Configured endpoints</div>
          <table className="admin-table">
            <thead><tr><th>Channel</th><th>Endpoint</th><th>Test result</th><th></th></tr></thead>
            <tbody>
              {[
                ['discord', config.webhooks?.DISCORD_WEBHOOK_URL],
                ['telegram', config.webhooks?.TELEGRAM_BOT_TOKEN],
              ].map(([ch, val]) => (
                <tr key={ch}>
                  <td style={{ textTransform: 'capitalize' }}>{ch}</td>
                  <td className="mono" style={{ fontSize: '0.75rem' }}>{val}</td>
                  <td>
                    {results[ch] && (
                      <span className={`badge ${results[ch].ok ? 'badge-ok' : 'badge-error'}`}>
                        {results[ch].ok ? 'delivered' : results[ch].error?.slice(0, 50)}
                      </span>
                    )}
                  </td>
                  <td>
                    <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                      onClick={() => testWebhook(ch)} disabled={testing[ch]}>
                      {testing[ch] ? 'Testing…' : `Test ${ch}`}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Page: Security ─────────────────────────────────────────────────────────

function PageSecurity({ toast }) {
  const [security, setSecurity] = useState(null)

  useEffect(() => {
    adminApi.get('/security').then(r => r.json()).then(setSecurity).catch(() => {})
  }, [])

  return (
    <div>
      <h1 className="admin-page-title">Security</h1>
      {security && !security.admin_key_set && (
        <div className="admin-callout admin-callout-amber">
          Admin API key not configured — routes are unauthenticated.
        </div>
      )}
      {security && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            {[
              { label: 'Admin key set', value: security.admin_key_set ? 'Yes' : 'No', warn: !security.admin_key_set },
              { label: 'Failed auth (24h)', value: security.failed_auth_last_24h, warn: security.failed_auth_last_24h > 0 },
              { label: 'Rate limit enabled', value: security.rate_limit_enabled ? 'Yes' : 'No' },
              { label: 'IOC limit / min', value: security.rate_limit_ioc_per_minute },
              { label: 'Refresh limit / min', value: security.rate_limit_refresh_per_minute },
            ].map(c => (
              <div key={c.label} className="admin-card" style={{ marginBottom: 0 }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>{c.label}</div>
                <div style={{ fontSize: '1.125rem', fontWeight: 700, color: c.warn ? 'var(--color-warn)' : 'var(--text-primary)' }}>{String(c.value)}</div>
              </div>
            ))}
          </div>
          <div className="admin-card">
            <div className="admin-card-title">Top rate-limit consumers</div>
            <table className="admin-table">
              <thead><tr><th>Client key</th><th>Hits</th></tr></thead>
              <tbody>
                {security.top_rate_limit_consumers?.length === 0 && (
                  <tr><td colSpan={2} style={{ color: 'var(--text-muted)' }}>None recorded yet</td></tr>
                )}
                {security.top_rate_limit_consumers?.map((c, i) => (
                  <tr key={i}><td className="mono" style={{ fontSize: '0.75rem' }}>{c.key}</td><td>{c.hits}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

// ── Page: Feed health ──────────────────────────────────────────────────────

function PageFeedHealth({ system, toast }) {
  const sources = system?.feeds?.sources || {}

  async function resetCircuit(sourceId) {
    try {
      await adminApi.post(`/feeds/${encodeURIComponent(sourceId)}/reset-circuit`, {})
      toast(`Circuit reset for ${sourceId}`, true)
    } catch (e) { toast(String(e.message), false) }
  }

  return (
    <div>
      <h1 className="admin-page-title">Feed health</h1>
      <div className="admin-card">
        <table className="admin-table">
          <thead>
            <tr><th>Source</th><th>Circuit</th><th>Failures</th><th>Last success</th><th>Last failure</th><th>Last error</th><th></th></tr>
          </thead>
          <tbody>
            {Object.keys(sources).length === 0 && (
              <tr><td colSpan={7} style={{ color: 'var(--text-muted)' }}>No health data yet — sources initialize on first fetch.</td></tr>
            )}
            {Object.entries(sources).map(([key, s]) => (
              <tr key={key}>
                <td>{sourceLabel(key)}</td>
                <td>
                  <span className={`badge ${s.circuit_open ? 'badge-error' : 'badge-ok'}`}>
                    {s.circuit_open ? 'open' : 'closed'}
                  </span>
                </td>
                <td>{s.consecutive_failures}</td>
                <td style={{ fontSize: '0.75rem' }}>{s.last_success || '—'}</td>
                <td style={{ fontSize: '0.75rem' }}>{s.last_failure || '—'}</td>
                <td style={{ fontSize: '0.75rem', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {s.last_error || ''}
                </td>
                <td>
                  <button className="admin-btn admin-btn-danger"
                    style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem' }}
                    disabled={!s.circuit_open}
                    onClick={() => resetCircuit(key)}>
                    Reset circuit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Page: Ingest log ───────────────────────────────────────────────────────

function PageIngestLog({ toast }) {
  const [logs, setLogs] = useState(null)
  const [level, setLevel] = useState('')
  const [reqId, setReqId] = useState('')
  const [limit, setLimit] = useState(100)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const intervalRef = useRef(null)

  async function loadLogs() {
    const params = new URLSearchParams({ limit })
    if (level) params.set('level', level)
    if (reqId) params.set('request_id', reqId)
    try {
      const res = await adminApi.get(`/logs?${params}`)
      setLogs(await res.json())
    } catch { }
  }

  useEffect(() => { loadLogs() }, [level, reqId, limit])

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(loadLogs, 10000)
    } else {
      clearInterval(intervalRef.current)
    }
    return () => clearInterval(intervalRef.current)
  }, [autoRefresh, level, reqId, limit])

  return (
    <div>
      <h1 className="admin-page-title">Ingest log</h1>
      <div className="admin-filter-bar">
        <select className="admin-select" value={level} onChange={e => setLevel(e.target.value)}>
          <option value="">All levels</option>
          {['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <input className="admin-input" placeholder="request_id…" value={reqId} onChange={e => setReqId(e.target.value)} style={{ minWidth: 180 }} />
        <select className="admin-select" value={limit} onChange={e => setLimit(Number(e.target.value))}>
          {[50, 100, 250, 500].map(n => <option key={n} value={n}>{n} entries</option>)}
        </select>
        <button className="admin-btn admin-btn-ghost" onClick={loadLogs}>Refresh</button>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
          <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
          Auto-refresh (10s)
        </label>
      </div>
      <div className="admin-card" style={{ padding: '0' }}>
        <table className="admin-table">
          <thead>
            <tr><th>Timestamp</th><th>Level</th><th>Logger</th><th>Message</th><th>Request ID</th></tr>
          </thead>
          <tbody>
            {logs === null && <tr><td colSpan={5} style={{ padding: '1rem', color: 'var(--text-muted)' }}>Loading…</td></tr>}
            {logs?.length === 0 && <tr><td colSpan={5} style={{ padding: '1rem', color: 'var(--text-muted)' }}>No logs in buffer</td></tr>}
            {logs?.map((entry, i) => (
              <tr key={i}>
                <td className="mono" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>{entry.ts}</td>
                <td><span className={`level-${entry.level}`} style={{ fontSize: '0.75rem', fontWeight: 600 }}>{entry.level}</span></td>
                <td className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{entry.logger}</td>
                <td style={{ fontSize: '0.8rem', wordBreak: 'break-word', maxWidth: 480 }}>{entry.message}</td>
                <td className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{entry.request_id || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Page: Audit log ────────────────────────────────────────────────────────

function PageAuditLog({ toast }) {
  const [data, setData] = useState(null)
  const [actionFilter, setActionFilter] = useState('')
  const [actorFilter, setActorFilter] = useState('')
  const [offset, setOffset] = useState(0)
  const limit = 100

  async function load() {
    const params = new URLSearchParams({ limit, offset })
    if (actionFilter) params.set('action', actionFilter)
    if (actorFilter) params.set('actor', actorFilter)
    try {
      const res = await adminApi.get(`/audit-log?${params}`)
      setData(await res.json())
    } catch { }
  }

  useEffect(() => { setOffset(0) }, [actionFilter, actorFilter])
  useEffect(() => { load() }, [actionFilter, actorFilter, offset])

  return (
    <div>
      <h1 className="admin-page-title">Audit log</h1>
      <div className="admin-filter-bar">
        <input className="admin-input" placeholder="Filter action…" value={actionFilter} onChange={e => setActionFilter(e.target.value)} />
        <input className="admin-input" placeholder="Filter actor…" value={actorFilter} onChange={e => setActorFilter(e.target.value)} />
      </div>
      <div className="admin-card">
        <table className="admin-table">
          <thead><tr><th>ID</th><th>Actor</th><th>Action</th><th>Target</th><th>Created at</th></tr></thead>
          <tbody>
            {data === null && <tr><td colSpan={5} style={{ color: 'var(--text-muted)' }}>Loading…</td></tr>}
            {data?.rows?.length === 0 && <tr><td colSpan={5} style={{ color: 'var(--text-muted)' }}>None</td></tr>}
            {data?.rows?.map(r => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td className="mono" style={{ fontSize: '0.75rem' }}>{r.actor || '—'}</td>
                <td className="mono" style={{ fontSize: '0.75rem' }}>{r.action}</td>
                <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.8rem' }}>{r.target || '—'}</td>
                <td style={{ fontSize: '0.75rem' }}>{fmtIso(r.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && (
          <div className="admin-pagination">
            <button className="admin-btn admin-btn-ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>← Prev</button>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
              {offset + 1}–{Math.min(offset + limit, data.total)} of {data.total}
            </span>
            <button className="admin-btn admin-btn-ghost" disabled={offset + limit >= data.total} onClick={() => setOffset(offset + limit)}>Next →</button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main AdminPage ─────────────────────────────────────────────────────────

export default function AdminPage() {
  const [page, setPage] = useState('overview')
  const [system, setSystem] = useState(null)
  const [keyModalOpen, setKeyModalOpen] = useState(false)
  const [modalError, setModalError] = useState('')
  const [authed, setAuthed] = useState(false)
  const { toasts, show: toast } = useToast()
  const pollRef = useRef(null)

  async function loadSystem() {
    try {
      const res = await adminApi.get('/system')
      if (!res.ok) throw Object.assign(new Error('Failed'), { status: res.status })
      const data = await res.json()
      setSystem(data)
      setAuthed(true)
      setKeyModalOpen(false)
      setModalError('')
    } catch (e) {
      if (e.status === 401) {
        setAuthed(false)
        setKeyModalOpen(true)
      }
    }
  }

  async function checkKeyRequired() {
    try {
      const res = await adminApi.get('/security')
      if (res.status === 401) {
        setKeyModalOpen(true)
        return
      }
      const data = await res.json()
      if (!data.admin_key_set) {
        setAuthed(true)
        await loadSystem()
      } else if (!getAdminKey()) {
        setKeyModalOpen(true)
      } else {
        await loadSystem()
      }
    } catch (e) {
      if (e.status === 401) {
        setKeyModalOpen(true)
      } else {
        await loadSystem()
      }
    }
  }

  useEffect(() => {
    checkKeyRequired()
    pollRef.current = setInterval(loadSystem, 30000)
    return () => clearInterval(pollRef.current)
  }, [])

  function handleKeySubmit(key) {
    setAdminKey(key)
    setModalError('')
    loadSystem().then(() => {
      if (!getAdminKey()) setModalError('Invalid key')
    })
  }

  async function handleRunIngest() {
    try {
      const res = await fetch('/api/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-BRIEFR-Admin-Key': getAdminKey(),
        },
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed')
      toast('Full ingest started', true)
    } catch (e) { toast(String(e.message), false) }
  }

  async function handleRestart() {
    try {
      await adminApi.post('/restart', {})
      toast('Restart initiated', true)
    } catch (e) { toast(String(e.message), false) }
  }

  const refreshInProgress = system?.refresh_in_progress || false

  const pages = {
    overview: <PageOverview system={system} />,
    backups: <PageBackups toast={toast} />,
    storage: <PageStorage toast={toast} />,
    watchlist: <PageWatchlist toast={toast} />,
    apikeys: <PageApiKeys toast={toast} />,
    scheduler: <PageScheduler toast={toast} />,
    webhooks: <PageWebhooks toast={toast} />,
    security: <PageSecurity toast={toast} />,
    feedhealth: <PageFeedHealth system={system} toast={toast} />,
    ingestlog: <PageIngestLog toast={toast} />,
    auditlog: <PageAuditLog toast={toast} />,
  }

  return (
    <div className="admin-root">
      {keyModalOpen && (
        <AdminPage_KeyModal onSubmit={handleKeySubmit} error={modalError} />
      )}
      <StatusBar
        system={system}
        onRunIngest={handleRunIngest}
        onRestart={handleRestart}
        refreshInProgress={refreshInProgress}
      />
      <div className="admin-body">
        <Sidebar activePage={page} setPage={setPage} system={system} />
        <div className="admin-content">
          {Object.entries(pages).map(([id, content]) => (
            <div key={id} className={`admin-page ${page === id ? 'active' : ''}`} id={`page-${id}`}>
              {content}
            </div>
          ))}
        </div>
      </div>
      <ToastArea toasts={toasts} />
    </div>
  )
}
