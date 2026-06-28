import { useState, useEffect } from 'react'
import { adminApi } from '../../api.js'
import DangerZone from './shared/DangerZone.jsx'
import GuardedPurgePanel from './shared/GuardedPurgePanel.jsx'
import HelpTip from './shared/HelpTip.jsx'
import { fmtAge, fmtIso } from './formatters.js'

export default function WatchlistPage({ toast, mode = 'operator' }) {
  const isAnalyst = mode === 'analyst'
  const [subtab, setSubtab] = useState('watchlist')
  const [watchlistState, setWatchlistState] = useState('all')
  const [watchlistRows, setWatchlistRows] = useState(null)
  const [iocRows, setIocRows] = useState(null)
  const [iocType, setIocType] = useState('')
  const [iocSearch, setIocSearch] = useState('')
  const [huntRows, setHuntRows] = useState(null)
  const [huntTechnique, setHuntTechnique] = useState('')

  useEffect(() => { if (isAnalyst) setSubtab('watchlist') }, [isAnalyst])

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
    try {
      const res = await adminApi.post('/watchlist/clear-snoozes', { confirm_text: 'clear' })
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
      <h1 className="admin-page-title">{isAnalyst ? 'Pinned CVEs' : 'Watchlist & cache'}</h1>
      <p className="admin-page-subtitle">
        {isAnalyst ? 'CVEs you’ve pinned to track.' : 'Manage pinned/snoozed CVEs, inspect the IOC lookup cache, and review hunt-pack matches.'}
      </p>
      {!isAnalyst && (
        <div className="admin-subtabs">
          {[
            ['watchlist', 'WATCHLIST', null],
            ['ioc', 'IOC CACHE', 'Indicator of Compromise results cached from threat-intel APIs (OTX, etc.). Populates automatically when analysts look up IPs, hashes, or domains from a CVE detail page.'],
            ['hunt', 'HUNT PACKS', 'Pre-computed detection packs grouped by MITRE ATT&CK technique. Created when a technique-based threat hunt is triggered from a CVE detail page.'],
          ].map(([id, label, tip]) => (
            <span key={id} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
              <button className={`admin-subtab ${subtab === id ? 'active' : ''}`} onClick={() => setSubtab(id)}>{label}</button>
              {tip && <HelpTip text={tip} />}
            </span>
          ))}
        </div>
      )}

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
          </div>
          {!isAnalyst && (
            <DangerZone title="Clear snoozes">
              <GuardedPurgePanel targets={[
                { target: 'watchlist_snoozes', title: 'Clear all snoozes', desc: 'Why: snoozed CVEs are hidden from the default watchlist view until you snooze again. What happens: removes every snooze entry. After: previously snoozed CVEs reappear in the default view; pinned CVEs are unaffected.', impact: `${snoozeCount} snoozed`, confirmWord: 'clear', run: clearSnoozes },
              ]} />
            </DangerZone>
          )}
          <div className="admin-card">
            <table className="admin-table">
              <thead><tr><th>CVE ID</th><th>SEVERITY</th><th>EPSS</th><th>KEV</th><th>STATE</th><th>CREATED</th><th></th></tr></thead>
              <tbody>
                {watchlistRows === null && <tr><td colSpan={7} className="admin-empty">Loading…</td></tr>}
                {watchlistRows?.length === 0 && <tr><td colSpan={7} className="admin-empty">{watchlistState === 'snooze' ? 'No snoozed CVEs' : watchlistState === 'pin' ? 'No pinned CVEs — pin CVEs from the main feed to track them here' : 'No watchlist entries yet — pin or snooze CVEs from the main feed to see them here'}</td></tr>}
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
          </div>
          <DangerZone title="Clear IOC cache">
            <GuardedPurgePanel targets={[
              { target: 'ioc_cache_all', title: 'Clear all IOC cache entries', desc: 'Why: IOC lookups are cached to avoid re-querying external threat-intel APIs on every page load. What happens: deletes every cached result below. After: the next lookup for each IOC is slower (re-fetches from the source API), but nothing is lost — the cache rebuilds itself automatically.', impact: `${iocRows?.length ?? 0} entries`, confirmWord: 'clear', run: clearAllIoc },
            ]} />
          </DangerZone>
          <div className="admin-card">
            <table className="admin-table">
              <thead><tr><th>VALUE</th><th>TYPE</th><th>CACHED AT</th><th>AGE</th><th></th></tr></thead>
              <tbody>
                {iocRows === null && <tr><td colSpan={5} className="admin-empty">Loading…</td></tr>}
                {iocRows?.length === 0 && <tr><td colSpan={5} className="admin-empty">{iocType || iocSearch ? 'No IOC cache entries match the current filters' : 'IOC cache is empty — lookups populate it automatically as you search indicators from CVE details'}</td></tr>}
                {iocRows?.map((r, i) => (
                  <tr key={i}>
                    <td className="mono" style={{ fontSize: '0.7rem', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.value}</td>
                    <td>{r.ioc_type}</td>
                    <td style={{ fontSize: '0.75rem' }}>{fmtIso(r.cached_at)}</td>
                    <td>{fmtAge(r.age_seconds)}</td>
                    <td>
                      <button className="admin-btn admin-btn-danger" style={{ fontSize: '0.7rem', padding: '0.1rem 0.35rem' }}
                        onClick={() => deleteIoc(r.value)}>Clear</button>
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
                {huntRows?.length === 0 && <tr><td colSpan={6} className="admin-empty">{huntTechnique ? 'No hunt packs match that technique ID' : 'No hunt packs yet — these are created when you run a technique-based threat hunt from a CVE detail page'}</td></tr>}
                {huntRows?.map(r => (
                  <tr key={r.id}>
                    <td>{r.id}</td>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>{r.technique_id}</td>
                    <td clas