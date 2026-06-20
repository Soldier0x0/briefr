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
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0; let val = bytes
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

function fmtIsoMono(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toISOString().replace('T', ' ').replace('Z', ' UTC') } catch { return iso }
}

function ageColor(seconds, greenMax, amberMax) {
  if (seconds === null || seconds === undefined) return ''
  if (seconds <= greenMax) return 'color-green'
  if (seconds <= amberMax) return 'color-amber'
  return 'color-red'
}

function diskPct(partition) {
  if (!partition || !partition.total || partition.total === 0) return 0
  return Math.round((partition.used / partition.total) * 100)
}

function diskBarColor(pct) {
  if (pct < 70) return 'green'
  if (pct < 90) return 'amber'
  return 'red'
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

// ── Confirm dialog ─────────────────────────────────────────────────────────

function ConfirmDialog({ title, message, confirmWord, onConfirm, onCancel }) {
  const [input, setInput] = useState('')
  return (
    <div className="admin-modal-overlay">
      <div className="admin-modal">
        <div className="admin-modal-title">{title}</div>
        <div className="admin-modal-body">{message}</div>
        {confirmWord && (
          <div style={{ marginTop: '1rem' }}>
            <label style={{ fontSize: '0.8125rem', color: 'var(--text2)', marginBottom: '0.4rem', display: 'block' }}>
              Type <code className="mono">{confirmWord}</code> to confirm
            </label>
            <input
              className="admin-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder={confirmWord}
              autoFocus
            />
          </div>
        )}
        <div className="admin-modal-actions">
          <button className="admin-btn admin-btn-ghost" onClick={onCancel}>Cancel</button>
          <button
            className="admin-btn admin-btn-danger"
            onClick={() => onConfirm(input)}
            disabled={confirmWord ? input !== confirmWord : false}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Status bar ─────────────────────────────────────────────────────────────

function StatusBar({ system, onRunIngest, onRestart, onDrainRestart, refreshInProgress }) {
  const [restartMenu, setRestartMenu] = useState(false)
  const [confirmRestart, setConfirmRestart] = useState(null) // null | 'immediate' | 'drain'
  const menuRef = useRef(null)

  useEffect(() => {
    function onDown(e) {
      if (restartMenu && menuRef.current && !menuRef.current.contains(e.target)) setRestartMenu(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [restartMenu])

  const nvdAge = system?.last_nvd_sync_age_seconds
  const backupAge = system?.last_backup_age_seconds
  const backupThreshold = system?.backup_threshold_seconds || 43200
  const openCircuits = system?.open_circuit_count || 0
  const integrityOk = system?.db_integrity?.ok !== false
  const discordConfigured = system?.feeds?.sources?.['webhook.discord']?.last_success
  const discordFailed = system?.feeds?.sources?.['webhook.discord']?.circuit_open
  const telegramConfigured = system?.feeds?.sources?.['webhook.telegram']?.last_success
  const telegramFailed = system?.feeds?.sources?.['webhook.telegram']?.circuit_open
  const commit = system?.version?.commit

  function discordPillClass() {
    if (!discordConfigured) return 'pill-gray'
    return discordFailed ? 'pill-amber' : 'pill-green'
  }

  function telegramPillClass() {
    if (!telegramConfigured) return 'pill-gray'
    return telegramFailed ? 'pill-amber' : 'pill-green'
  }

  return (
    <>
      {confirmRestart && (
        <ConfirmDialog
          title={confirmRestart === 'drain' ? 'Drain then restart' : 'Restart now?'}
          message={
            confirmRestart === 'drain'
              ? 'Wait for all running jobs to finish, then restart the backend process.'
              : 'Immediately restart the backend. Any in-progress jobs will be interrupted.'
          }
          onConfirm={() => {
            setConfirmRestart(null)
            if (confirmRestart === 'drain') onDrainRestart()
            else onRestart()
          }}
          onCancel={() => setConfirmRestart(null)}
        />
      )}
      <div className="admin-statusbar">
        <span className="sb-item">
          <span className="sb-label">CVEs</span>
          <span className="sb-value">{system?.cve_count?.toLocaleString() ?? '…'}</span>
        </span>
        <div className="sb-sep" />
        <span className="sb-item">
          <span className="sb-label">NVD sync</span>
          <span className={`sb-value ${nvdAge > 7200 ? 'sb-warn' : ''}`}>
            {nvdAge != null ? fmtAge(nvdAge) : '—'}
          </span>
        </span>
        {backupAge != null && (
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
          <span className={`pill ${discordPillClass()}`}>Discord</span>
        </span>
        <span className="sb-item">
          <span className={`pill ${telegramPillClass()}`}>Telegram</span>
        </span>
        {commit && (
          <>
            <div className="sb-sep" />
            <span className="sb-item">
              <span className="sb-label mono" style={{ fontSize: '0.6875rem' }}>{commit.slice(0, 7) || 'dev'}</span>
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
          <div className="admin-split-btn" ref={menuRef}>
            <button
              className="admin-btn admin-btn-ghost admin-split-btn-main"
              onClick={() => setConfirmRestart('immediate')}
              style={{ fontSize: '0.75rem' }}
            >
              Restart now
            </button>
            <button
              className="admin-btn admin-btn-ghost admin-split-btn-arrow"
              onClick={() => setRestartMenu(v => !v)}
              aria-label="Restart options"
              style={{ fontSize: '0.75rem' }}
            >▾</button>
            {restartMenu && (
              <div className="admin-split-menu">
                <button className="admin-split-menu-item" onClick={() => { setRestartMenu(false); setConfirmRestart('immediate') }}>Restart now</button>
                <button className="admin-split-menu-item" onClick={() => { setRestartMenu(false); setConfirmRestart('drain') }}>Drain then restart</button>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}

// ── Sidebar nav ────────────────────────────────────────────────────────────

const NAV = [
  { section: 'OVERVIEW', items: [{ id: 'overview', label: 'System health', badgeKey: 'jobs_with_errors_count' }] },
  { section: 'DATA', items: [
    { id: 'backups', label: 'Backups' },
    { id: 'storage', label: 'Storage' },
    { id: 'watchlist', label: 'Watchlist & cache' },
  ]},
  { section: 'CONFIGURATION', items: [
    { id: 'apikeys', label: 'API keys & config' },
    { id: 'scheduler', label: 'Scheduler' },
    { id: 'webhooks', label: 'Webhooks' },
    { id: 'security', label: 'Security', badgeKey: 'failed_auth_last_24h' },
  ]},
  { section: 'FEEDS', items: [
    { id: 'feedhealth', label: 'Feed health', badgeKey: 'open_circuit_count' },
    { id: 'ingestlog', label: 'Ingest log', badgeKey: 'ingest_error_count' },
  ]},
  { section: 'AUDIT', items: [
    { id: 'auditlog', label: 'Audit log' },
  ]},
  { section: 'COMING SOON', items: [
    { id: 'coming-login', label: 'App login & sessions', locked: true, tooltip: 'Ships in V1.4 / T3-S0' },
    { id: 'coming-users', label: 'Multi-user management', locked: true, tooltip: 'Ships in V2.0' },
    { id: 'coming-postgres', label: 'Postgres migration', locked: true, tooltip: 'Ships in V2.0' },
    { id: 'coming-ratelimit', label: 'Rate limit dashboard', locked: true, tooltip: 'Ships in V1.4' },
  ]},
]

function Sidebar({ activePage, setPage, system, ingestErrorCount }) {
  const openCircuits = system?.open_circuit_count || 0
  const failedAuth = system?.failed_auth_last_24h || 0
  const jobErrors = system?.jobs_with_errors_count || 0

  function getBadge(item) {
    if (item.badgeKey === 'open_circuit_count') return openCircuits
    if (item.badgeKey === 'failed_auth_last_24h') return failedAuth
    if (item.badgeKey === 'jobs_with_errors_count') return jobErrors
    if (item.badgeKey === 'ingest_error_count') return ingestErrorCount
    return 0
  }

  return (
    <nav className="admin-sidebar">
      {NAV.map(section => (
        <div key={section.section}>
          <div className="nav-section-label">{section.section}</div>
          {section.items.map(item => {
            const badge = getBadge(item)
            if (item.locked) {
              return (
                <div
                  key={item.id}
                  className="nav-item nav-item-locked"
                  onClick={() => setPage(item.id)}
                  title={item.tooltip}
                >
                  <span className="nav-lock-icon">🔒</span>
                  <span>{item.label}</span>
                  {item.tooltip && <span className="nav-item-tooltip">{item.tooltip}</span>}
                </div>
              )
            }
            return (
              <div
                key={item.id}
                className={`nav-item ${activePage === item.id ? 'active' : ''}`}
                onClick={() => setPage(item.id)}
              >
                {item.label}
                {badge > 0 && <span className={`nav-badge ${item.badgeKey === 'failed_auth_last_24h' ? 'nav-badge-amber' : 'nav-badge-red'}`}>{badge}</span>}
              </div>
            )
          })}
        </div>
      ))}
    </nav>
  )
}

// ── Stat card ──────────────────────────────────────────────────────────────

function StatCard({ label, value, subLabel, colorClass, valueStyle }) {
  return (
    <div className="stat-card">
      <div className="stat-card-label">{label}</div>
      <div className={`stat-card-value ${colorClass || ''}`} style={valueStyle}>{value ?? '—'}</div>
      {subLabel && <div className="stat-card-sub">{subLabel}</div>}
    </div>
  )
}

// ── Job status badge ───────────────────────────────────────────────────────

function JobStatusBadge({ status }) {
  const map = {
    ACTIVE: 'badge-ok',
    PAUSED: 'badge-warn',
    LOCKED: 'badge-info',
    DISABLED: 'badge-muted',
  }
  return <span className={`badge ${map[status] || 'badge-muted'}`}>{status}</span>
}

// ── Scheduler job table (shared by overview & scheduler pages) ─────────────

function JobTable({ jobs, onRunNow, onPauseResume, expandErrors = true }) {
  const [expanded, setExpanded] = useState({})
  if (!jobs) return <div className="admin-empty">Loading…</div>
  if (jobs.length === 0) return <div className="admin-empty">No jobs registered</div>

  return (
    <table className="admin-table">
      <thead>
        <tr>
          <th>JOB ID</th><th>NAME</th><th>STATUS</th><th>LAST RUN</th>
          <th>DURATION</th><th>RECORDS</th><th>ERROR</th><th>NEXT RUN</th><th>ACTIONS</th>
        </tr>
      </thead>
      <tbody>
        {jobs.map(job => (
          <>
            <tr key={job.id}>
              <td className="mono" style={{ fontSize: '0.7rem' }}>{job.id}</td>
              <td style={{ fontSize: '0.8rem' }}>{job.name}</td>
              <td><JobStatusBadge status={job.status} /></td>
              <td style={{ fontSize: '0.75rem' }}>{fmtIso(job.last_run_utc)}</td>
              <td>{fmtDur(job.last_run_duration_seconds)}</td>
              <td>{job.last_run_records_upserted ?? '—'}</td>
              <td>
                {job.last_run_had_error === true ? (
                  <button
                    className="badge badge-error"
                    style={{ cursor: expandErrors ? 'pointer' : 'default', background: 'none', border: 'none' }}
                    onClick={() => expandErrors && setExpanded(e => ({ ...e, [job.id]: !e[job.id] }))}
                  >
                    ERROR {expandErrors ? (expanded[job.id] ? '▲' : '▼') : ''}
                  </button>
                ) : job.last_run_had_error === false ? '' : '—'}
              </td>
              <td style={{ fontSize: '0.75rem' }}>{job.status === 'PAUSED' ? '—' : fmtIso(job.next_run_time)}</td>
              <td>
                <div style={{ display: 'flex', gap: '0.3rem' }}>
                  {onRunNow && (
                    <button
                      className="admin-btn admin-btn-ghost"
                      style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem' }}
                      onClick={() => onRunNow(job.id)}
                      disabled={job.status === 'LOCKED'}
                    >Run</button>
                  )}
                  {onPauseResume && (
                    <button
                      className={`admin-btn ${job.status === 'PAUSED' ? 'admin-btn-primary' : 'admin-btn-warn'}`}
                      style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem' }}
                      onClick={() => onPauseResume(job)}
                    >
                      {job.status === 'PAUSED' ? 'Resume' : 'Pause'}
                    </button>
                  )}
                </div>
              </td>
            </tr>
            {expandErrors && expanded[job.id] && job.last_error_message && (
              <tr key={`${job.id}-err`}>
                <td colSpan={9} style={{ background: 'var(--bg3)', padding: '0.5rem 0.75rem' }}>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--red)', wordBreak: 'break-all' }}>
                    {job.last_error_message}
                  </div>
                  {onRunNow && (
                    <button
                      className="admin-btn admin-btn-ghost"
                      style={{ marginTop: '0.4rem', fontSize: '0.75rem' }}
                      onClick={() => onRunNow(job.id)}
                    >
                      Retry now
                    </button>
                  )}
                </td>
              </tr>
            )}
          </>
        ))}
      </tbody>
    </table>
  )
}

// ── Page: Overview / System health ─────────────────────────────────────────

function PageOverview({ system, toast }) {
  const [diagResult, setDiagResult] = useState(null)
  const [intResult, setIntResult] = useState(null)
  const [running, setRunning] = useState({})
  const [showDiag, setShowDiag] = useState(false)

  async function runNow(jobId) {
    setRunning(r => ({ ...r, [jobId]: true }))
    try {
      const res = await adminApi.post('/scheduler/run', { job_id: jobId })
      const data = await res.json()
      if (res.status === 409) { toast('Already running — check active locks', false); return }
      toast(data.ok ? `Job started: ${jobId}` : data.detail, data.ok)
    } catch (e) { toast(String(e.message), false) }
    setTimeout(() => setRunning(r => ({ ...r, [jobId]: false })), 2000)
  }

  async function pauseResume(job) {
    const action = job.status === 'PAUSED' ? 'resume' : 'pause'
    try {
      const res = await adminApi.post(`/scheduler/${action}`, { job_id: job.id })
      const data = await res.json()
      toast(data.ok ? `Job ${action}d` : 'Failed', data.ok)
    } catch (e) { toast(String(e.message), false) }
  }

  async function runSmoke() {
    setRunning(r => ({ ...r, smoke: true }))
    try {
      const res = await adminApi.post('/diagnostics/smoke', {})
      const data = await res.json()
      setDiagResult(data)
      setShowDiag(true)
    } catch (e) { toast(String(e.message), false) }
    setRunning(r => ({ ...r, smoke: false }))
  }

  async function runIntegrity() {
    setRunning(r => ({ ...r, integrity: true }))
    try {
      const res = await adminApi.post('/diagnostics/integrity', {})
      const data = await res.json()
      setIntResult(data)
      setShowDiag(true)
    } catch (e) { toast(String(e.message), false) }
    setRunning(r => ({ ...r, integrity: false }))
  }

  if (!system) return <div className="admin-empty">Loading…</div>

  const { db_integrity, scheduler_jobs, active_locks, recent_errors } = system
  const nvdAgeColor = ageColor(system.last_nvd_sync_age_seconds, 7200, 14400)
  const backupAgeColor = ageColor(system.last_backup_age_seconds, 28800, 43200)

  return (
    <div>
      <h1 className="admin-page-title">System health</h1>

      {/* Stat cards */}
      <div className="stat-card-row">
        <StatCard label="CVE COUNT" value={system.cve_count?.toLocaleString()} />
        <StatCard label="NVD SYNC AGE" value={fmtAge(system.last_nvd_sync_age_seconds)} colorClass={nvdAgeColor} />
        <StatCard label="LAST BACKUP" value={fmtAge(system.last_backup_age_seconds)} colorClass={backupAgeColor} />
        <StatCard label="DB INTEGRITY" value={db_integrity?.ok ? 'OK' : 'FAILED'} colorClass={db_integrity?.ok ? 'color-green' : 'color-red'} />
        <StatCard label="OPEN CIRCUITS" value={system.open_circuit_count ?? 0} colorClass={system.open_circuit_count > 0 ? 'color-red' : 'color-green'} />
        <StatCard label="JOBS WITH ERRORS" value={system.jobs_with_errors_count ?? 0} colorClass={system.jobs_with_errors_count > 0 ? 'color-red' : 'color-green'} />
      </div>

      {/* Quick diagnostics */}
      <div className="admin-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: showDiag ? '0.75rem' : 0 }}>
          <span className="admin-card-title" style={{ marginBottom: 0 }}>Quick diagnostics</span>
          <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={runSmoke} disabled={running.smoke}>
            {running.smoke ? <><span className="admin-spinner" /> Running…</> : 'Run smoke test'}
          </button>
          <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={runIntegrity} disabled={running.integrity}>
            {running.integrity ? <><span className="admin-spinner" /> Checking…</> : 'Check DB integrity'}
          </button>
          {showDiag && <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.7rem' }} onClick={() => setShowDiag(false)}>Hide</button>}
        </div>
        {showDiag && diagResult && (
          <div style={{ marginTop: '0.5rem' }}>
            <div style={{ marginBottom: '0.25rem', fontSize: '0.75rem', color: diagResult.ok ? 'var(--green)' : 'var(--red)' }}>
              {diagResult.ok ? '✓ All checks passed' : '✗ Some checks failed'} ({diagResult.duration_ms}ms)
            </div>
            {diagResult.checks?.map((c, i) => (
              <div key={i} style={{ fontSize: '0.8125rem', display: 'flex', gap: '0.5rem', padding: '0.2rem 0' }}>
                <span style={{ color: c.passed ? 'var(--green)' : 'var(--red)' }}>{c.passed ? '✓' : '✗'}</span>
                <span>{c.name}</span>
                <span style={{ color: 'var(--text3)' }}>{c.detail}</span>
              </div>
            ))}
          </div>
        )}
        {showDiag && intResult && (
          <div style={{ marginTop: '0.5rem', fontSize: '0.8125rem' }}>
            <span style={{ color: intResult.integrity_ok ? 'var(--green)' : 'var(--red)' }}>
              {intResult.integrity_ok ? '✓ Integrity OK' : '✗ Integrity FAILED'}
            </span>
            {' — '}
            <span style={{ color: intResult.foreign_keys_ok ? 'var(--green)' : 'var(--red)' }}>
              {intResult.foreign_keys_ok ? '✓ FK OK' : `✗ ${intResult.foreign_key_violations} FK violations`}
            </span>
          </div>
        )}
      </div>

      {/* Two-column: active locks + recent errors */}
      <div className="admin-two-col">
        <div className="admin-card" style={{ flex: 1 }}>
          <div className="admin-card-title">Active locks</div>
          {(!active_locks || active_locks.length === 0) ? (
            <div className="admin-empty">No jobs running</div>
          ) : (
            <table className="admin-table">
              <thead><tr><th>JOB ID</th><th>LOCK</th></tr></thead>
              <tbody>
                {active_locks.map(l => (
                  <tr key={l.job_id}>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{l.job_id}</td>
                    <td><span className="badge badge-info">LOCKED</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="admin-card" style={{ flex: 1 }}>
          <div className="admin-card-title">Recent errors</div>
          {(!recent_errors || recent_errors.length === 0) ? (
            <div className="admin-empty" style={{ color: 'var(--green)' }}>All jobs clean</div>
          ) : (
            <table className="admin-table">
              <thead><tr><th>JOB ID</th><th>ERROR</th><th>LAST RUN</th><th></th></tr></thead>
              <tbody>
                {recent_errors.map(e => (
                  <tr key={e.job_id}>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{e.job_id}</td>
                    <td style={{ fontSize: '0.75rem', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.error || '—'}</td>
                    <td style={{ fontSize: '0.75rem' }}>{fmtIso(e.last_run_utc)}</td>
                    <td><button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem' }} onClick={() => runNow(e.job_id)}>Retry</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Full scheduler table */}
      <div className="admin-card">
        <div className="admin-card-title">Scheduler jobs</div>
        <JobTable jobs={scheduler_jobs} onRunNow={runNow} onPauseResume={pauseResume} />
      </div>
    </div>
  )
}

// ── Page: Backups ──────────────────────────────────────────────────────────

function PageBackups({ toast, system }) {
  const [backups, setBackups] = useState(null)
  const [loading, setLoading] = useState(false)
  const [verifyResults, setVerifyResults] = useState({})
  const [page, setPage] = useState(0)
  const pageSize = 20
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
    setVerifyResults(r => ({ ...r, [filename]: 'checking' }))
    try {
      const res = await adminApi.post(`/backups/verify/${encodeURIComponent(filename)}`, {})
      const data = await res.json()
      setVerifyResults(r => ({ ...r, [filename]: data }))
      toast(data.ok ? `Verified: ${data.details}` : `Verify failed: ${data.details}`, data.ok)
    } catch (e) {
      setVerifyResults(r => ({ ...r, [filename]: { ok: false, details: String(e.message) } }))
    }
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

  const lastBackupAge = system?.last_backup_age_seconds
  const backupAgeColor = ageColor(lastBackupAge, 28800, 43200)
  const archiveCount = backups?.length ?? 0
  const integrityOk = system?.db_integrity?.ok

  const paged = (backups || []).slice(page * pageSize, (page + 1) * pageSize)

  return (
    <div>
      <h1 className="admin-page-title">Backups</h1>

      <div className="stat-card-row">
        <StatCard label="LAST BACKUP" value={fmtAge(lastBackupAge)} colorClass={backupAgeColor} />
        <StatCard label="ARCHIVE COUNT" value={archiveCount} />
        <StatCard label="DB INTEGRITY" value={integrityOk ? 'OK' : 'FAILED'} colorClass={integrityOk ? 'color-green' : 'color-red'} />
      </div>

      <div className="admin-action-bar" style={{ justifyContent: 'flex-end' }}>
        <button className="admin-btn admin-btn-primary" onClick={runBackup} disabled={loading}>
          {loading ? <><span className="admin-spinner" /> Running…</> : 'Run backup now'}
        </button>
        <button className="admin-btn admin-btn-ghost" onClick={() => fileInputRef.current?.click()}>
          Upload archive
        </button>
        <input ref={fileInputRef} type="file" accept=".tar.gz,.age" style={{ display: 'none' }} onChange={uploadBackup} />
      </div>

      <div className="admin-card">
        <table className="admin-table">
          <thead>
            <tr><th>FILENAME</th><th>SIZE</th><th>AGE</th><th>ENCRYPTED</th><th>INTEGRITY</th><th>REASON</th><th>ACTIONS</th></tr>
          </thead>
          <tbody>
            {backups === null && <tr><td colSpan={7} className="admin-empty">Loading…</td></tr>}
            {backups?.length === 0 && <tr><td colSpan={7} className="admin-empty">No backups found</td></tr>}
            {paged.map(b => {
              const vr = verifyResults[b.filename]
              return (
                <tr key={b.filename}>
                  <td className="mono" style={{ fontSize: '0.7rem' }}>{b.filename}</td>
                  <td>{fmtBytes(b.size_bytes)}</td>
                  <td>{fmtAge(b.created_at ? (Date.now() / 1000 - new Date(b.created_at).getTime() / 1000) : null)}</td>
                  <td>{b.encrypted ? <span className="badge badge-info">ENC</span> : <span className="badge badge-muted">plain</span>}</td>
                  <td>
                    {vr && vr !== 'checking' ? (
                      <span className={`badge ${vr.ok ? 'badge-ok' : 'badge-error'}`}>{vr.ok ? 'OK' : 'FAILED'}</span>
                    ) : (
                      <span className={`badge ${b.integrity === 'ok' ? 'badge-ok' : 'badge-warn'}`}>{b.integrity}</span>
                    )}
                  </td>
                  <td style={{ fontSize: '0.75rem' }}>{b.reason || '—'}</td>
                  <td>
                    <button
                      className="admin-btn admin-btn-ghost"
                      style={{ fontSize: '0.7rem', padding: '0.15rem 0.4rem' }}
                      onClick={() => verifyBackup(b.filename)}
                      disabled={vr === 'checking'}
                    >
                      {vr === 'checking' ? <span className="admin-spinner" /> : 'Verify'}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {(backups || []).length > pageSize && (
          <div className="admin-pagination">
            <button className="admin-btn admin-btn-ghost" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
            <span style={{ color: 'var(--text3)', fontSize: '0.8125rem' }}>
              {page * pageSize + 1}–{Math.min((page + 1) * pageSize, backups.length)} of {backups.length}
            </span>
            <button className="admin-btn admin-btn-ghost" disabled={(page + 1) * pageSize >= backups.length} onClick={() => setPage(p => p + 1)}>Next →</button>
          </div>
        )}
      </div>

      <div className="admin-callout admin-callout-amber" style={{ marginTop: '1rem' }}>
        <strong>Restore is a CLI operation</strong> to prevent accidental data loss.<br />
        <code className="mono">bash /opt/briefr/deploy/briefr-restore.sh</code><br />
        To restore specific archive: <code className="mono">briefr-restore.sh {'<filename>'}</code>
      </div>
    </div>
  )
}

// ── Page: Storage ──────────────────────────────────────────────────────────

function PageStorage({ toast }) {
  const [storage, setStorage] = useState(null)
  const [confirm, setConfirm] = useState(null) // {target, word, extra}

  const load = useCallback(async () => {
    try {
      const res = await adminApi.get('/storage')
      setStorage(await res.json())
    } catch { }
  }, [])

  useEffect(() => { load() }, [load])

  async function doPurge(target, confirmText, extra = {}) {
    try {
      const res = await adminApi.post('/storage/purge', { target, confirm_text: confirmText, ...extra })
      const data = await res.json()
      toast(data.ok ? `Purged ${data.rows_deleted} rows from ${target}` : `Purge failed: ${data.detail || 'error'}`, data.ok)
      if (data.ok) load()
    } catch (e) { toast(String(e.message), false) }
  }

  async function exportDb() {
    window.location.href = '/api/admin/storage/export'
  }

  const dbPartition = storage?.db_partition || {}
  const backupPartition = storage?.backup_partition || {}
  const dbPct = diskPct(dbPartition)
  const backupPct = diskPct(backupPartition)

  const maxTableRows = Math.max(1, ...Object.values(storage?.tables || {}).map(v => v || 0))

  const purgeCards = [
    { target: 'ioc_cache', title: 'Clear IOC cache', desc: 'Deletes all rows from ioc_cache. Next lookups will re-query external APIs.', confirmWord: 'clear', impact: `${storage?.tables?.ioc_cache ?? 0} rows` },
    { target: 'feed_cache', title: 'Clear feed cache', desc: 'Deletes all rows from feed_cache. Next incident feed load will be slower.', confirmWord: 'clear', impact: `${storage?.tables?.feed_cache ?? 0} rows` },
    { target: 'epss_history_old', title: 'Prune EPSS history (>90 days)', desc: 'Deletes epss_history rows older than 90 days.', confirmWord: 'prune', impact: '~' + storage?.tables?.epss_history ?? '?' + ' total rows' },
    { target: 'change_history_old', title: 'Prune change history (>90 days)', desc: 'Deletes cve_change_history rows older than 90 days.', confirmWord: 'prune', impact: `${storage?.tables?.cve_change_history ?? 0} total rows` },
    { target: 'rejected_cves', title: 'Remove rejected CVEs', desc: "Removes CVEs with 'Rejected reason:' in description.", confirmWord: 'purge', impact: 'varies' },
    { target: 'epss_backfill_reset', title: 'Re-trigger EPSS backfill', desc: 'Clears the epss_backfill_done marker. Next startup re-runs full backfill.', confirmWord: null, impact: 'not destructive' },
    { target: 'nvd_watermark', title: 'NVD backfill reset', desc: 'Clears the NVD sync watermark. Next NVD sync re-fetches from NVD_DAYS_BACK days ago.', confirmWord: 'backfill', impact: 'triggers full re-ingest', extraDaysBack: true },
  ]

  return (
    <div>
      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.desc}
          confirmWord={confirm.word}
          onConfirm={(inputText) => {
            setConfirm(null)
            doPurge(confirm.target, inputText, confirm.extra || {})
          }}
          onCancel={() => setConfirm(null)}
        />
      )}

      <h1 className="admin-page-title">Storage</h1>

      <div className="admin-action-bar" style={{ justifyContent: 'flex-end' }}>
        <button className="admin-btn admin-btn-ghost" onClick={exportDb} title={`DB: ${fmtBytes(storage?.db_size_bytes)}`}>
          Download DB
        </button>
      </div>

      {storage && (
        <div className="admin-card">
          <div className="admin-card-title">Disk usage</div>
          <div className="admin-two-col" style={{ gap: '1.5rem', marginBottom: '0.75rem' }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text3)', marginBottom: '0.25rem' }}>DB partition</div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text2)', marginBottom: '0.25rem' }}>
                {fmtBytes(dbPartition.used)} / {fmtBytes(dbPartition.total)} ({dbPct}%)
              </div>
              <div className="disk-bar">
                <div className={`disk-bar-fill disk-bar-fill-${diskBarColor(dbPct)}`} style={{ width: `${dbPct}%` }} />
              </div>
              <div style={{ marginTop: '0.3rem', fontSize: '0.7rem', color: 'var(--text3)' }}>
                DB file: {storage.db_path} ({fmtBytes(storage.db_size_bytes)})
              </div>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text3)', marginBottom: '0.25rem' }}>Backup partition</div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text2)', marginBottom: '0.25rem' }}>
                {fmtBytes(backupPartition.used)} / {fmtBytes(backupPartition.total)} ({backupPct}%)
              </div>
              <div className="disk-bar">
                <div className={`disk-bar-fill disk-bar-fill-${diskBarColor(backupPct)}`} style={{ width: `${backupPct}%` }} />
              </div>
              <div style={{ marginTop: '0.3rem', fontSize: '0.7rem', color: 'var(--text3)' }}>
                {storage.archive_count ?? 0} archives in {storage.backup_dir}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="admin-card">
        <div className="admin-card-title">Table row counts</div>
        <table className="admin-table">
          <thead><tr><th>TABLE</th><th style={{ width: '140px' }}>SIZE</th><th style={{ textAlign: 'right' }}>ROWS</th></tr></thead>
          <tbody>
            {Object.entries(storage?.tables || {}).map(([t, c]) => {
              const pct = c > 0 ? Math.max(2, Math.round((c / maxTableRows) * 100)) : 0
              return (
                <tr key={t}>
                  <td className="mono" style={{ fontSize: '0.75rem' }}>{t}</td>
                  <td>
                    <div style={{ height: '6px', background: 'var(--bg3)', borderRadius: '3px', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${pct}%`, background: 'var(--border-strong)', borderRadius: '3px' }} />
                    </div>
                  </td>
                  <td style={{ textAlign: 'right' }}>{c === -1 ? 'n/a' : c.toLocaleString()}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Purge controls</div>
        <div className="purge-grid">
          {purgeCards.map(pc => (
            <div key={pc.target} className="purge-card">
              <div className="purge-card-title">{pc.title}</div>
              <div className="purge-card-desc">{pc.desc}</div>
              <div className="purge-card-impact">Impact: {pc.impact}</div>
              <button
                className="admin-btn admin-btn-danger"
                style={{ marginTop: '0.5rem', fontSize: '0.75rem' }}
                onClick={() => {
                  if (!pc.confirmWord) {
                    doPurge(pc.target, '', {})
                  } else {
                    setConfirm({ target: pc.target, title: pc.title, desc: pc.desc, word: pc.confirmWord })
                  }
                }}
              >
                {pc.target === 'epss_backfill_reset' ? 'Reset' : 'Purge'}
              </button>
            </div>
          ))}
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
    const params = new URLSearchParams({ limit: 50 })
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

  const pinCount = watchlistRows?.filter(r => r.state === 'pin').length ?? 0
  const snoozeCount = watchlistRows?.filter(r => r.state === 'snooze').length ?? 0

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

  async function clearAllIoc() {
    if (!window.confirm('Clear all IOC cache entries?')) return
    try {
      const res = await adminApi.post('/storage/purge', { target: 'ioc_cache', confirm_text: 'clear' })
      const data = await res.json()
      toast(`Cleared ${data.rows_deleted} IOC cache entries`, data.ok)
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

  const iocOldestAge = iocRows?.length
    ? Math.max(...iocRows.map(r => r.age_seconds || 0))
    : null

  return (
    <div>
      <h1 className="admin-page-title">Watchlist & cache</h1>
      <div className="admin-subtabs">
        {[['watchlist', 'WATCHLIST'], ['ioc', 'IOC CACHE'], ['hunt', 'HUNT PACKS']].map(([id, label]) => (
          <button key={id} className={`admin-subtab ${subtab === id ? 'active' : ''}`} onClick={() => setSubtab(id)}>{label}</button>
        ))}
      </div>

      {subtab === 'watchlist' && (
        <div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--text3)', marginBottom: '0.75rem' }}>
            {pinCount} pinned CVEs · {snoozeCount} snoozed CVEs
          </div>
          <div className="admin-action-bar">
            <div className="admin-filter-chips">
              {['all', 'pin', 'snooze'].map(s => (
                <button key={s} className={`filter-chip ${watchlistState === s ? 'active' : ''}`} onClick={() => setWatchlistState(s)}>
                  {s === 'snooze' ? 'Snoozed' : s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
            <button className="admin-btn admin-btn-warn" style={{ marginLeft: 'auto' }} onClick={clearSnoozes}>
              Clear all snoozes
            </button>
          </div>
          <div className="admin-card">
            <table className="admin-table">
              <thead><tr><th>CVE ID</th><th>SEVERITY</th><th>EPSS</th><th>KEV</th><th>STATE</th><th>CREATED</th><th></th></tr></thead>
              <tbody>
                {watchlistRows === null && <tr><td colSpan={7} className="admin-empty">Loading…</td></tr>}
                {watchlistRows?.length === 0 && <tr><td colSpan={7} className="admin-empty">No entries</td></tr>}
                {watchlistRows?.map(r => (
                  <tr key={r.cve_id}>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{r.cve_id}</td>
                    <td>{r.severity || '—'}</td>
                    <td>{r.epss_score != null ? (r.epss_score * 100).toFixed(1) + '%' : '—'}</td>
                    <td>{r.is_kev ? <span className="badge badge-error">KEV</span> : ''}</td>
                    <td><span className={`badge ${r.state === 'pin' ? 'badge-info' : 'badge-warn'}`}>{r.state}</span></td>
                    <td style={{ fontSize: '0.75rem' }}>{fmtIso(r.created_at)}</td>
                    <td>
                      <button className="admin-btn admin-btn-danger" style={{ fontSize: '0.7rem', padding: '0.1rem 0.35rem' }}
                        onClick={() => removeWatchlist(r.cve_id)}>Remove</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {subtab === 'ioc' && (
        <div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--text3)', marginBottom: '0.75rem' }}>
            {iocRows?.length ?? 0} entries
            {iocOldestAge ? ` · oldest ${fmtAge(iocOldestAge)}` : ''}
          </div>
          <div className="admin-filter-bar">
            <select className="admin-select" value={iocType} onChange={e => setIocType(e.target.value)}>
              <option value="">All types</option>
              <option value="ip">IP</option>
              <option value="hash">Hash</option>
              <option value="domain">Domain</option>
            </select>
            <input className="admin-input" placeholder="Search value…" value={iocSearch} onChange={e => setIocSearch(e.target.value)} />
            <button className="admin-btn admin-btn-danger" style={{ marginLeft: 'auto', fontSize: '0.75rem' }} onClick={clearAllIoc}>
              Clear all
            </button>
          </div>
          <div className="admin-card">
            <table className="admin-table">
              <thead><tr><th>VALUE</th><th>TYPE</th><th>CACHED AT</th><th>AGE</th><th></th></tr></thead>
              <tbody>
                {iocRows === null && <tr><td colSpan={5} className="admin-empty">Loading…</td></tr>}
                {iocRows?.length === 0 && <tr><td colSpan={5} className="admin-empty">No entries</td></tr>}
                {iocRows?.map((r, i) => (
                  <tr key={i}>
                    <td className="mono" style={{ fontSize: '0.7rem', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.value}</td>
                    <td>{r.ioc_type}</td>
                    <td style={{ fontSize: '0.75rem' }}>{fmtIso(r.cached_at)}</td>
                    <td>{fmtAge(r.age_seconds)}</td>
                    <td>
                      <button className="admin-btn admin-btn-danger" style={{ fontSize: '0.7rem', padding: '0.1rem 0.35rem' }}
                        onClick={() => deleteIoc(r.value)}>Expire</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {subtab === 'hunt' && (
        <div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--text3)', marginBottom: '0.75rem' }}>
            {huntRows?.length ?? 0} packs
          </div>
          <div className="admin-filter-bar">
            <input className="admin-input" placeholder="Filter by technique ID…" value={huntTechnique} onChange={e => setHuntTechnique(e.target.value)} />
          </div>
          <div className="admin-card">
            <table className="admin-table">
              <thead><tr><th>PACK ID</th><th>TECHNIQUE</th><th>CVE</th><th>PRIORITY</th><th>CREATED</th><th></th></tr></thead>
              <tbody>
                {huntRows === null && <tr><td colSpan={6} className="admin-empty">Loading…</td></tr>}
                {huntRows?.length === 0 && <tr><td colSpan={6} className="admin-empty">No hunt packs</td></tr>}
                {huntRows?.map(r => (
                  <tr key={r.id}>
                    <td>{r.id}</td>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{r.technique_id}</td>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{r.cve_id}</td>
                    <td>{r.priority}</td>
                    <td style={{ fontSize: '0.75rem' }}>{fmtIso(r.created_at)}</td>
                    <td>
                      <button className="admin-btn admin-btn-danger" style={{ fontSize: '0.7rem', padding: '0.1rem 0.35rem' }}
                        onClick={() => deleteHunt(r.id)}>Delete</button>
                    </td>
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
        <div className="admin-modal-overlay">
          <div className="admin-modal" style={{ minWidth: 480 }}>
            <div className="admin-modal-title">Review pending changes</div>
            <table className="admin-table" style={{ marginTop: '0.5rem' }}>
              <thead><tr><th>KEY</th><th>NEW VALUE</th></tr></thead>
              <tbody>
                {Object.entries(queue).map(([k, v]) => (
                  <tr key={k}>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{k}</td>
                    <td style={{ fontSize: '0.8125rem' }}>{k.endsWith('_KEY') || k.endsWith('_TOKEN') || k.endsWith('_SECRET') ? '••••' : v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="admin-modal-actions">
              <button className="admin-btn admin-btn-ghost" onClick={() => setShowDiff(false)}>Close</button>
              <button className="admin-btn admin-btn-danger" onClick={() => { setQueue({}); setShowDiff(false) }}>Discard all</button>
              <button className="admin-btn admin-btn-primary" onClick={() => { setShowDiff(false); applyAll() }} disabled={applying}>
                Write & restart
              </button>
            </div>
          </div>
        </div>
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

// ── Page: Scheduler ────────────────────────────────────────────────────────

const MANUAL_PIPELINES = [
  { id: 'nvd_incremental_sync', label: 'NVD only' },
  { id: 'kev_metadata_sync', label: 'KEV only' },
  { id: 'epss_score_sync', label: 'EPSS only' },
  { id: 'weekly_mitre_refresh', label: 'MITRE + ATLAS' },
  { id: 'incident_feed_refresh', label: 'Incident RSS' },
  { id: 'nightly_correlation', label: 'Correlation' },
]

function PageScheduler({ toast, system }) {
  const [jobs, setJobs] = useState(null)
  const [running, setRunning] = useState({})
  const [pauseAllConfirm, setPauseAllConfirm] = useState(false)

  async function loadJobs() {
    try {
      const res = await adminApi.get('/scheduler')
      setJobs(await res.json())
    } catch { }
  }

  useEffect(() => { loadJobs() }, [])

  async function runNow(jobId) {
    setRunning(r => ({ ...r, [jobId]: true }))
    try {
      const res = await adminApi.post('/scheduler/run', { job_id: jobId })
      const data = await res.json()
      if (res.status === 409) { toast('Already running', false); return }
      toast(data.ok ? `Started: ${jobId}` : data.detail || 'Failed', data.ok)
      setTimeout(loadJobs, 1000)
    } catch (e) { toast(String(e.message), false) }
    setTimeout(() => setRunning(r => ({ ...r, [jobId]: false })), 2000)
  }

  async function pauseResume(job) {
    const action = job.status === 'PAUSED' ? 'resume' : 'pause'
    try {
      await adminApi.post(`/scheduler/${action}`, { job_id: job.id })
      toast(`Job ${action}d`, true)
      loadJobs()
    } catch (e) { toast(String(e.message), false) }
  }

  async function pauseAll() {
    setPauseAllConfirm(false)
    const jobList = jobs || []
    for (const job of jobList) {
      if (job.status === 'ACTIVE') {
        await adminApi.post('/scheduler/pause', { job_id: job.id })
      }
    }
    toast('All active jobs paused', true)
    loadJobs()
  }

  async function resumeAll() {
    const jobList = jobs || []
    for (const job of jobList) {
      if (job.status === 'PAUSED') {
        await adminApi.post('/scheduler/resume', { job_id: job.id })
      }
    }
    toast('All paused jobs resumed', true)
    loadJobs()
  }

  const activeLocks = system?.active_locks || []

  return (
    <div>
      {pauseAllConfirm && (
        <ConfirmDialog
          title="Pause all jobs?"
          message="This will pause all active scheduler jobs. No scheduled syncs will run until resumed."
          onConfirm={pauseAll}
          onCancel={() => setPauseAllConfirm(false)}
        />
      )}

      <h1 className="admin-page-title">Scheduler</h1>

      <div className="admin-card">
        <div className="admin-card-title">Manual triggers</div>
        <div className="admin-action-bar" style={{ flexWrap: 'wrap' }}>
          {MANUAL_PIPELINES.map(p => {
            const job = (jobs || []).find(j => j.id === p.id)
            const locked = job?.status === 'LOCKED' || running[p.id]
            return (
              <button
                key={p.id}
                className="admin-btn admin-btn-ghost"
                style={{ fontSize: '0.8125rem' }}
                onClick={() => runNow(p.id)}
                disabled={locked}
              >
                {locked ? <><span className="admin-spinner" /> Running…</> : p.label}
              </button>
            )
          })}
        </div>
        {activeLocks.length > 0 && (
          <div style={{ fontSize: '0.75rem', color: 'var(--amber)', marginTop: '0.5rem' }}>
            {activeLocks.map(l => l.job_id).join(', ')} currently running
          </div>
        )}
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Global controls</div>
        <div className="admin-action-bar">
          <button className="admin-btn admin-btn-danger" onClick={() => setPauseAllConfirm(true)}>Pause all jobs</button>
          <button className="admin-btn admin-btn-primary" onClick={resumeAll}>Resume all jobs</button>
        </div>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">All jobs</div>
        <JobTable jobs={jobs} onRunNow={runNow} onPauseResume={pauseResume} />
      </div>
    </div>
  )
}

// ── Page: Webhooks ─────────────────────────────────────────────────────────

function PageWebhooks({ toast }) {
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
                Additional channels (Slack, PagerDuty) ship in V1.4.
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

// ── Page: Security ─────────────────────────────────────────────────────────

function PageSecurity({ toast }) {
  const [security, setSecurity] = useState(null)
  const [rotateOpen, setRotateOpen] = useState(false)
  const [rotateValue, setRotateValue] = useState('')

  useEffect(() => {
    adminApi.get('/security').then(r => r.json()).then(setSecurity).catch(() => {})
  }, [])

  function generateKey() {
    const arr = new Uint8Array(24)
    crypto.getRandomValues(arr)
    return btoa(String.fromCharCode(...arr)).replace(/[+/=]/g, c => ({ '+': '-', '/': '_', '=': '' }[c]))
  }

  async function saveRotatedKey() {
    if (!rotateValue.trim()) return
    try {
      const res = await adminApi.post('/config/apply-all', [{ key: 'BRIEFR_ADMIN_API_KEY', value: rotateValue }])
      const data = await res.json()
      if (res.ok) {
        setAdminKey(rotateValue)
        toast('Admin key rotated. Backend restarting…', true)
        setRotateOpen(false)
      } else {
        toast(data.detail || 'Failed to rotate key', false)
      }
    } catch (e) { toast(String(e.message), false) }
  }

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
          <div className="stat-card-row">
            <StatCard label="RATE LIMIT" value={security.rate_limit_enabled ? 'ON' : 'OFF'} colorClass={security.rate_limit_enabled ? 'color-green' : 'color-amber'} />
            <StatCard label="IOC LIMIT / MIN" value={security.rate_limit_ioc_per_minute} />
            <StatCard label="REFRESH LIMIT / MIN" value={security.rate_limit_refresh_per_minute} />
            <StatCard label="ADMIN KEY" value={security.admin_key_set ? 'SET' : 'NOT SET'} colorClass={security.admin_key_set ? 'color-green' : 'color-red'} />
            <StatCard label="AUTH FAILURES (24H)" value={security.failed_auth_last_24h} colorClass={security.failed_auth_last_24h > 0 ? 'color-red' : 'color-green'} />
          </div>

          <div className="admin-card">
            <div className="admin-card-title">Admin key</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span className={`badge ${security.admin_key_set ? 'badge-ok' : 'badge-error'}`}>
                {security.admin_key_set ? 'SET' : 'NOT SET'}
              </span>
              <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.8125rem' }} onClick={() => { setRotateOpen(v => !v); setRotateValue(generateKey()) }}>
                Rotate key
              </button>
            </div>
            {rotateOpen && (
              <div style={{ marginTop: '0.75rem' }}>
                <div style={{ fontSize: '0.8125rem', color: 'var(--text3)', marginBottom: '0.4rem' }}>
                  New key (edit or use generated):
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <input className="admin-input" style={{ minWidth: 300, fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}
                    value={rotateValue} onChange={e => setRotateValue(e.target.value)} />
                  <button className="admin-btn admin-btn-primary" style={{ fontSize: '0.8rem' }} onClick={saveRotatedKey}>
                    Save & restart
                  </button>
                  <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.8rem' }} onClick={() => setRotateOpen(false)}>
                    Cancel
                  </button>
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text3)', marginTop: '0.4rem' }}>
                  Backend will restart immediately after saving. You will be logged out.
                </div>
              </div>
            )}
          </div>

          <div className="admin-card">
            <div className="admin-card-title">Auth failures (last 24h)</div>
            <div className="admin-callout admin-callout-amber" style={{ fontSize: '0.8rem' }}>
              No app login yet. Auth failure tracking will appear here in V1.4 / T3-S0.
            </div>
            {security.failed_auth_last_24h > 0 ? (
              <div style={{ marginTop: '0.5rem', fontSize: '0.8125rem', color: 'var(--red)' }}>
                {security.failed_auth_last_24h} auth failure(s) in last 24h
              </div>
            ) : (
              <div style={{ marginTop: '0.5rem', fontSize: '0.8125rem', color: 'var(--green)' }}>
                No auth failures in last 24h
              </div>
            )}
          </div>

          <div className="admin-card">
            <div className="admin-card-title">Top rate-limit consumers</div>
            <table className="admin-table">
              <thead><tr><th>CLIENT KEY</th><th>HITS</th></tr></thead>
              <tbody>
                {security.top_rate_limit_consumers?.length === 0 && (
                  <tr><td colSpan={2} className="admin-empty">None recorded yet</td></tr>
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
  const incidents = system?.feeds?.incidents

  async function resetCircuit(sourceId) {
    try {
      await adminApi.post(`/feeds/${encodeURIComponent(sourceId)}/reset-circuit`, {})
      toast(`Circuit reset for ${sourceId}`, true)
    } catch (e) { toast(String(e.message), false) }
  }

  async function rebuildFeed() {
    try {
      const res = await adminApi.post('/scheduler/run', { job_id: 'incident_feed_refresh' })
      const data = await res.json()
      toast(data.ok ? 'Incident feed rebuild started' : data.detail || 'Failed', data.ok)
    } catch (e) { toast(String(e.message), false) }
  }

  // Sort: circuit_open first, then by consecutive_failures desc
  const sorted = Object.entries(sources).sort(([, a], [, b]) => {
    if (a.circuit_open !== b.circuit_open) return b.circuit_open ? 1 : -1
    return (b.consecutive_failures || 0) - (a.consecutive_failures || 0)
  })

  return (
    <div>
      <h1 className="admin-page-title">Feed health</h1>

      <div className="feed-card-grid">
        {sorted.map(([key, s]) => {
          let borderColor = 'var(--border)'
          if (s.circuit_open) borderColor = 'var(--red)'
          else if (s.consecutive_failures > 0) borderColor = 'var(--amber)'
          return (
            <div key={key} className="feed-source-card" style={{ borderLeftColor: borderColor }}>
              <div className="feed-source-name">{sourceLabel(key)}</div>
              <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', margin: '0.4rem 0' }}>
                <span className={`badge ${s.circuit_open ? 'badge-error' : 'badge-ok'}`}>
                  {s.circuit_open ? 'OPEN' : 'CLOSED'}
                </span>
                {s.consecutive_failures > 0 && (
                  <span className="badge badge-warn">{s.consecutive_failures} fail{s.consecutive_failures !== 1 ? 's' : ''}</span>
                )}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text3)' }}>
                {s.last_success ? `✓ ${fmtIso(s.last_success)}` : 'Never succeeded'}
              </div>
              {s.last_error && (
                <div style={{ fontSize: '0.7rem', color: 'var(--amber)', marginTop: '0.2rem', wordBreak: 'break-all' }}>
                  {s.last_error.slice(0, 80)}
                </div>
              )}
              <button
                className="admin-btn admin-btn-danger"
                style={{ marginTop: '0.5rem', fontSize: '0.7rem', padding: '0.15rem 0.5rem' }}
                disabled={!s.circuit_open}
                onClick={() => resetCircuit(key)}
              >
                Reset circuit
              </button>
            </div>
          )
        })}
        {sorted.length === 0 && (
          <div className="admin-empty" style={{ gridColumn: '1/-1' }}>No health data yet — sources initialize on first fetch.</div>
        )}
      </div>

      {incidents && (
        <div className="admin-card" style={{ marginTop: '1rem' }}>
          <div className="admin-card-title">Incidents snapshot</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <div>
              <span className={`badge ${incidents.stale ? 'badge-warn' : 'badge-ok'}`}>
                {incidents.stale ? 'STALE' : 'FRESH'}
              </span>
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text2)' }}>
              Last built: {fmtIso(incidents.last_refresh)}
            </div>
            <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={rebuildFeed}>
              Rebuild now
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Page: Ingest log ───────────────────────────────────────────────────────

function PageIngestLog({ toast, onErrorCountChange }) {
  const [logData, setLogData] = useState(null)
  const [level, setLevel] = useState('')
  const [loggerFilter, setLoggerFilter] = useState('')
  const [reqId, setReqId] = useState('')
  const [limit, setLimit] = useState(100)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const intervalRef = useRef(null)

  const logs = logData?.logs || []
  const knownLoggers = logData?.known_loggers || []

  async function loadLogs() {
    const params = new URLSearchParams({ limit })
    if (level) params.set('level', level)
    if (loggerFilter) params.set('logger', loggerFilter)
    if (reqId) params.set('request_id', reqId)
    try {
      const res = await adminApi.get(`/logs?${params}`)
      const data = await res.json()
      setLogData(data)
      // Count errors for sidebar badge
      if (onErrorCountChange) {
        const errorCount = (data.logs || []).filter(e => e.level === 'ERROR' || e.level === 'CRITICAL').length
        onErrorCountChange(errorCount)
      }
    } catch { }
  }

  useEffect(() => { loadLogs() }, [level, loggerFilter, reqId, limit])

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(loadLogs, 10000)
    } else {
      clearInterval(intervalRef.current)
    }
    return () => clearInterval(intervalRef.current)
  }, [autoRefresh, level, loggerFilter, reqId, limit])

  function exportLogs() {
    const lines = logs.map(e => JSON.stringify(e)).join('\n')
    const blob = new Blob([lines], { type: 'application/x-ndjson' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `briefr-logs-${new Date().toISOString().slice(0, 10)}.ndjson`
    a.click()
    URL.revokeObjectURL(url)
  }

  function rowStyle(entry) {
    if (entry.level === 'ERROR' || entry.level === 'CRITICAL') return { background: 'rgba(232,85,51,0.05)' }
    return {}
  }

  return (
    <div>
      <h1 className="admin-page-title">Ingest log</h1>
      <div className="admin-filter-bar">
        <select className="admin-select" value={level} onChange={e => setLevel(e.target.value)}>
          <option value="">All levels</option>
          {['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <select className="admin-select" value={loggerFilter} onChange={e => setLoggerFilter(e.target.value)}>
          <option value="">All loggers</option>
          {knownLoggers.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <input className="admin-input" placeholder="request_id…" value={reqId} onChange={e => setReqId(e.target.value)} style={{ minWidth: 160 }} />
        <select className="admin-select" value={limit} onChange={e => setLimit(Number(e.target.value))}>
          {[50, 100, 250, 500].map(n => <option key={n} value={n}>{n} entries</option>)}
        </select>
        <button className="admin-btn admin-btn-ghost" onClick={loadLogs}>Refresh</button>
        <button className="admin-btn admin-btn-ghost" onClick={exportLogs} title="Export as NDJSON">Export logs</button>
        <label className="admin-toggle-label">
          <div className="admin-toggle-wrap">
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
            <span className="admin-toggle-slider" />
          </div>
          Auto (10s)
        </label>
      </div>
      <div className="admin-card" style={{ padding: 0 }}>
        <table className="admin-table">
          <thead>
            <tr><th>TIMESTAMP</th><th>LEVEL</th><th>LOGGER</th><th>MESSAGE</th><th>REQUEST ID</th></tr>
          </thead>
          <tbody>
            {logs.length === 0 && !logData && <tr><td colSpan={5} className="admin-empty">Loading…</td></tr>}
            {logs.length === 0 && logData && <tr><td colSpan={5} className="admin-empty">No logs in buffer</td></tr>}
            {logs.map((entry, i) => (
              <tr key={i} style={rowStyle(entry)}>
                <td className="mono" style={{ fontSize: '0.68rem', whiteSpace: 'nowrap' }}>{entry.ts}</td>
                <td>
                  <span className={`level-badge level-${entry.level}`}>{entry.level}</span>
                </td>
                <td className="mono" style={{ fontSize: '0.68rem', color: 'var(--text3)' }}>{entry.logger}</td>
                <td style={{ fontSize: '0.8rem', wordBreak: 'break-word', maxWidth: 480, color: entry.level === 'ERROR' || entry.level === 'CRITICAL' ? 'var(--red)' : undefined }}>
                  {entry.message}
                </td>
                <td className="mono" style={{ fontSize: '0.68rem', color: 'var(--text3)' }}>{entry.request_id || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Page: Audit log ────────────────────────────────────────────────────────

const AUDIT_PREFIXES = ['backup', 'refresh', 'scheduler', 'storage', 'config', 'system', 'webhook', 'watchlist', 'feed', 'diagnostics']

function PageAuditLog({ toast }) {
  const [data, setData] = useState(null)
  const [activePrefix, setActivePrefix] = useState('')
  const [offset, setOffset] = useState(0)
  const limit = 100

  async function load(prefix = '', off = 0) {
    const params = new URLSearchParams({ limit, offset: off })
    if (prefix) params.set('action_prefix', prefix)
    try {
      const res = await adminApi.get(`/audit-log?${params}`)
      setData(await res.json())
      setOffset(off)
      setActivePrefix(prefix)
    } catch { }
  }

  useEffect(() => { load() }, [])

  return (
    <div>
      <h1 className="admin-page-title">Audit log</h1>
      <div className="admin-filter-chips" style={{ marginBottom: '0.75rem' }}>
        <button className={`filter-chip ${activePrefix === '' ? 'active' : ''}`} onClick={() => load('', 0)}>All</button>
        {AUDIT_PREFIXES.map(p => (
          <button key={p} className={`filter-chip ${activePrefix === p + '.' ? 'active' : ''}`} onClick={() => load(p + '.', 0)}>
            {p}.*
          </button>
        ))}
      </div>
      <div className="admin-card">
        <table className="admin-table">
          <thead><tr><th>ID</th><th>ACTOR</th><th>ACTION</th><th>TARGET</th><th>CREATED AT</th></tr></thead>
          <tbody>
            {data === null && <tr><td colSpan={5} className="admin-empty">Loading…</td></tr>}
            {data?.rows?.length === 0 && <tr><td colSpan={5} className="admin-empty">No entries</td></tr>}
            {data?.rows?.map(r => (
              <tr key={r.id}>
                <td style={{ fontSize: '0.75rem' }}>{r.id}</td>
                <td className="mono" style={{ fontSize: '0.75rem' }}>{r.actor || '—'}</td>
                <td className="mono" style={{ fontSize: '0.75rem' }}>{r.action}</td>
                <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.8rem' }}>{r.target || '—'}</td>
                <td className="mono" style={{ fontSize: '0.7rem' }}>{fmtIsoMono(r.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && (
          <div className="admin-pagination">
            <button className="admin-btn admin-btn-ghost" disabled={offset === 0} onClick={() => load(activePrefix, Math.max(0, offset - limit))}>← Prev</button>
            <span style={{ color: 'var(--text3)', fontSize: '0.8125rem' }}>
              {offset + 1}–{Math.min(offset + limit, data.total)} of {data.total}
            </span>
            <button className="admin-btn admin-btn-ghost" disabled={offset + limit >= data.total} onClick={() => load(activePrefix, offset + limit)}>Load more →</button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Coming soon placeholder page ───────────────────────────────────────────

const COMING_SOON_INFO = {
  'coming-login': {
    title: 'App login & sessions',
    message: 'Ships in V1.4 (T3-S0). Adds built-in auth, httpOnly session cookies, login page, and audit_log.actor population.',
  },
  'coming-users': {
    title: 'Multi-user management',
    message: 'Ships in V2.0. The users table schema is already designed (id, email, password_hash, role, is_active, created_at) and will be activated when multi-user is enabled.',
  },
  'coming-postgres': {
    title: 'Postgres migration',
    message: 'Ships in V2.0. To migrate: set DATABASE_URL to a postgres:// connection string, set NVD_DAYS_BACK=3650 and restart. The scheduler will refill from NVD. Keep SQLite as fallback until Postgres is confirmed stable.',
  },
  'coming-ratelimit': {
    title: 'Rate limit dashboard',
    message: 'Ships in V1.4. Will show per-IP bucket levels, top consumers, and allow per-IP block/allowlist.',
  },
}

function PageComingSoon({ pageId, setPage }) {
  const info = COMING_SOON_INFO[pageId] || { title: 'Coming soon', message: 'This feature is under development.' }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '4rem 2rem', textAlign: 'center' }}>
      <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🔒</div>
      <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.75rem' }}>{info.title}</h2>
      <p style={{ fontSize: '0.9rem', color: 'var(--text2)', maxWidth: 480, lineHeight: 1.6, marginBottom: '1.5rem' }}>{info.message}</p>
      <button className="admin-btn admin-btn-ghost" onClick={() => setPage('overview')}>← Back to System health</button>
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
  const [ingestErrorCount, setIngestErrorCount] = useState(0)
  const { toasts, show: toast } = useToast()
  const pollRef = useRef(null)

  async function loadSystem() {
    try {
      const res = await adminApi.get('/system')
      if (res.status === 401) {
        setAuthed(false); setKeyModalOpen(true); return
      }
      if (!res.ok) return
      const data = await res.json()
      setSystem(data); setAuthed(true); setKeyModalOpen(false); setModalError('')
    } catch (e) {
      if (e?.status === 401) { setAuthed(false); setKeyModalOpen(true) }
    }
  }

  async function checkKeyRequired() {
    try {
      const res = await adminApi.get('/security')
      if (res.status === 401) { setKeyModalOpen(true); return }
      if (!res.ok) { await loadSystem(); return }
      const data = await res.json()
      if (!data.admin_key_set) { setAuthed(true); await loadSystem() }
      else if (!getAdminKey()) { setKeyModalOpen(true) }
      else { await loadSystem() }
    } catch (e) {
      if (e?.status === 401) setKeyModalOpen(true)
      else await loadSystem()
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
      if (!authed && !getAdminKey()) setModalError('Invalid key')
    })
  }

  async function handleRunIngest() {
    try {
      const res = await fetch('/api/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-BRIEFR-Admin-Key': getAdminKey() },
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

  async function handleDrainRestart() {
    try {
      await adminApi.post('/restart', { drain: true })
      toast('Drain initiated — backend will restart when jobs complete', true)
    } catch (e) { toast(String(e.message), false) }
  }

  const isComingSoon = page.startsWith('coming-')

  const pageContent = isComingSoon ? (
    <PageComingSoon pageId={page} setPage={setPage} />
  ) : {
    overview: <PageOverview system={system} toast={toast} />,
    backups: <PageBackups toast={toast} system={system} />,
    storage: <PageStorage toast={toast} />,
    watchlist: <PageWatchlist toast={toast} />,
    apikeys: <PageApiKeys toast={toast} />,
    scheduler: <PageScheduler toast={toast} system={system} />,
    webhooks: <PageWebhooks toast={toast} />,
    security: <PageSecurity toast={toast} />,
    feedhealth: <PageFeedHealth system={system} toast={toast} />,
    ingestlog: <PageIngestLog toast={toast} onErrorCountChange={setIngestErrorCount} />,
    auditlog: <PageAuditLog toast={toast} />,
  }[page] || <div className="admin-empty">Page not found</div>

  return (
    <div className="admin-root">
      {keyModalOpen && (
        <AdminPage_KeyModal onSubmit={handleKeySubmit} error={modalError} />
      )}
      <StatusBar
        system={system}
        onRunIngest={handleRunIngest}
        onRestart={handleRestart}
        onDrainRestart={handleDrainRestart}
        refreshInProgress={system?.refresh_in_progress || false}
      />
      <div className="admin-body">
        <Sidebar activePage={page} setPage={setPage} system={system} ingestErrorCount={ingestErrorCount} />
        <div className="admin-content">
          {pageContent}
        </div>
      </div>
      <ToastArea toasts={toasts} />
    </div>
  )
}
