import { useState, useEffect } from 'react'
import { adminApi } from '../../api.js'
import ConfirmModal from './shared/ConfirmModal.jsx'
import { fmtAge, fmtIso } from './formatters.js'

export default function WatchlistPage({ toast }) {
  const [subtab, setSubtab] = useState('watchlist')
  const [watchlistState, setWatchlistState] = useState('all')
  const [watchlistRows, setWatchlistRows] = useState(null)
  const [iocRows, setIocRows] = useState(null)
  const [iocType, setIocType] = useState('')
  const [iocSearch, setIocSearch] = useState('')
  const [huntRows, setHuntRows] = useState(null)
  const [huntTechnique, setHuntTechnique] = useState('')
  const [confirmClearSnoozes, setConfirmClearSnoozes] = useState(false)
  const [confirmClearIoc, setConfirmClearIoc] = useState(false)

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
      {confirmClearSnoozes && (
        <ConfirmModal
          title="Clear all snoozes?"
          message="This removes every legacy snooze entry from the watchlist table."
          confirmWord="clear"
          onConfirm={() => { setConfirmClearSnoozes(false); clearSnoozes() }}
          onCancel={() => setConfirmClearSnoozes(false)}
        />
      )}
      {confirmClearIoc && (
        <ConfirmModal
          title="Clear all IOC cache entries?"
          message="Deletes all rows from ioc_cache. Next lookups will re-query external APIs."
          confirmWord="clear"
          onConfirm={() => { setConfirmClearIoc(false); clearAllIoc() }}
          onCancel={() => setConfirmClearIoc(false)}
        />
      )}

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
            <button className="admin-btn admin-btn-warn" style={{ marginLeft: 'auto' }} onClick={() => setConfirmClearSnoozes(true)}>
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
            <button className="admin-btn admin-btn-danger" style={{ marginLeft: 'auto', fontSize: '0.75rem' }} onClick={() => setConfirmClearIoc(true)}>
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
