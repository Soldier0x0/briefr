import { useState, useEffect } from 'react'
import { adminApi } from '../../api.js'
import { Select } from '../../components/ui/index.js'
import DangerZone from './shared/DangerZone.jsx'
import GuardedPurgePanel from './shared/GuardedPurgePanel.jsx'
import HelpTip from './shared/HelpTip.jsx'
import { DOMAIN_TERM_TIPS } from '../../utils/domainTermTips.js'
import { toggleChipSelection } from '../../utils/toggleChipSelection.js'
import { fmtAge, fmtIso } from './formatters.js'
import ToggleSwitch from './shared/ToggleSwitch.jsx'
import { AdminTableBodySkeletonRows } from './shared/AdminSkeletons.jsx'

const TRIGGER_LABELS = [
  ['kev', 'CISA KEV'],
  ['epss', 'EPSS jump'],
  ['poc', 'Public PoC'],
  ['patch', 'Patch available'],
  ['withdrawn', 'Withdrawn / rejected'],
]

function adminErrText(e) {
  const msg = String(e?.message || e)
  return e?.requestId ? `${msg} (ref: ${e.requestId})` : msg
}

function TableLoadError({ colSpan, error, onRetry, compact = false }) {
  return (
    <tr>
      <td colSpan={colSpan} className={compact ? 'admin-empty admin-empty--compact' : 'admin-empty'}>
        <span className="admin-inline-error" role="alert">{adminErrText(error)}</span>
        {' '}
        <button type="button" className="admin-btn admin-btn-ghost" onClick={onRetry}>Retry</button>
      </td>
    </tr>
  )
}

function TriggerRow({ id, label, on, onChange, disabled }) {
  const switchId = `watchlist-trigger-${id}`
  return (
    <div className="admin-pref-row">
      <label className="admin-pref-label mono" htmlFor={switchId}>{label}</label>
      <ToggleSwitch
        id={switchId}
        on={on}
        onChange={onChange}
        disabled={disabled}
      />
    </div>
  )
}

export default function WatchlistPage({ toast, mode = 'operator' }) {
  const isAnalyst = mode === 'analyst'
  const [subtab, setSubtab] = useState('watchlist')
  const [watchlistState, setWatchlistState] = useState('all')
  const [watchlistRows, setWatchlistRows] = useState(null)
  const [iocRows, setIocRows] = useState(null)
  const [iocType, setIocType] = useState('')
  const [iocSearch, setIocSearch] = useState('')
  const [huntRows, setHuntRows] = useState(null)
  const [watchlistError, setWatchlistError] = useState(null)
  const [iocError, setIocError] = useState(null)
  const [huntError, setHuntError] = useState(null)
  const [huntTechnique, setHuntTechnique] = useState('')
  const [policy, setPolicy] = useState(null)
  const [policySaving, setPolicySaving] = useState(false)
  const [policyLoading, setPolicyLoading] = useState(false)
  const [policyError, setPolicyError] = useState(null)

  async function loadPolicy() {
    setPolicyError(null)
    setPolicyLoading(true)
    try {
      const data = await adminApi.getJson('/watchlist/policy')
      setPolicy(data)
    } catch (e) {
      setPolicyError(e)
    } finally {
      setPolicyLoading(false)
    }
  }

  useEffect(() => { if (isAnalyst) setSubtab('watchlist') }, [isAnalyst])

  async function loadWatchlist() {
    setWatchlistError(null)
    setWatchlistRows(null)
    try {
      const { data } = await adminApi.getJson(`/watchlist?state=${watchlistState}&limit=200`)
      setWatchlistRows(Array.isArray(data) ? data : [])
    } catch (e) {
      setWatchlistError(e)
      setWatchlistRows([])
    }
  }

  async function loadIoc() {
    const params = new URLSearchParams({ limit: 50 })
    if (iocType) params.set('ioc_type', iocType)
    if (iocSearch) params.set('search', iocSearch)
    setIocError(null)
    setIocRows(null)
    try {
      const { data } = await adminApi.getJson(`/ioc-cache?${params}`)
      setIocRows(Array.isArray(data) ? data : [])
    } catch (e) {
      setIocError(e)
      setIocRows([])
    }
  }

  async function loadHunts() {
    const params = new URLSearchParams({ limit: 100 })
    if (huntTechnique) params.set('technique_id', huntTechnique)
    setHuntError(null)
    setHuntRows(null)
    try {
      const { data } = await adminApi.getJson(`/hunt-packs?${params}`)
      setHuntRows(Array.isArray(data) ? data : [])
    } catch (e) {
      setHuntError(e)
      setHuntRows([])
    }
  }

  useEffect(() => { if (subtab === 'watchlist') loadWatchlist() }, [subtab, watchlistState])
  useEffect(() => { if (subtab === 'watchlist' && !isAnalyst) loadPolicy() }, [subtab, isAnalyst])
  useEffect(() => { if (subtab === 'ioc') loadIoc() }, [subtab, iocType, iocSearch])
  useEffect(() => { if (subtab === 'hunt') loadHunts() }, [subtab, huntTechnique])

  const pinCount = watchlistRows?.filter(r => r.state === 'pin').length ?? 0
  const snoozeCount = watchlistRows?.filter(r => r.state === 'snooze').length ?? 0
  const allTriggersOn = policy && TRIGGER_LABELS.every(([id]) => policy.triggers?.[id])

  async function updateTrigger(id, on) {
    if (!policy || policySaving) return
    const next = {
      ...policy,
      triggers: { ...policy.triggers, [id]: on },
    }
    setPolicySaving(true)
    try {
      const saved = await adminApi.putJson('/watchlist/policy', next)
      setPolicy(saved)
      toast('Watchlist alert policy saved', true)
    } catch (e) {
      toast(String(e.message), false)
    } finally {
      setPolicySaving(false)
    }
  }

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
            ['watchlist', 'WATCHLIST', DOMAIN_TERM_TIPS.watchlistSubtab],
            ['ioc', 'IOC CACHE', 'Indicator of Compromise results cached from threat-intel APIs (OTX, etc.). Populates automatically when analysts look up IPs, hashes, or domains from a CVE detail page.'],
            ['hunt', 'HUNT PACKS', 'Pre-computed detection packs grouped by MITRE ATT&CK technique. Created when a technique-based threat hunt is triggered from a CVE detail page.'],
          ].map(([id, label, tip]) => (
            <span key={id} className="admin-subtab-item">
              <button className={`admin-subtab ${subtab === id ? 'active' : ''}`} onClick={() => setSubtab(id)}>{label}</button>
              {tip && <HelpTip text={tip} />}
            </span>
          ))}
        </div>
      )}

      {subtab === 'watchlist' && (
        <div>
          {!isAnalyst && (
            <div className="admin-card">
              <h2 className="admin-card-title">
                Alert triggers
                <HelpTip text="Real-time pinned-CVE alerts — not the daily brief. Quiet default: KEV, EPSS jumps, PoC, and withdrawn. Patch is off. Turning every trigger on sends a digest instead of a firehose." />
              </h2>
              {policyError ? (
                <p className="admin-page-subtitle admin-inline-error" role="alert">
                  Failed to load policy: {String(policyError.message || policyError)}{' '}
                  <button type="button" className="admin-btn admin-btn-ghost" onClick={loadPolicy}>Retry</button>
                </p>
              ) : policyLoading || !policy ? (
                <p className="admin-page-subtitle" role="status">Loading alert policy…</p>
              ) : (
                <>
                  <p className="admin-page-subtitle">
                    {allTriggersOn
                      ? 'All triggers on — delivery is digest (one combined alert per CVE per run).'
                      : 'Per-change alerts for enabled triggers. Overrides per CVE are rare and stored in policy JSON.'}
                  </p>
                  <div className="admin-watchlist-triggers">
                    {TRIGGER_LABELS.map(([id, label]) => (
                      <TriggerRow
                        key={id}
                        id={id}
                        label={label}
                        on={!!policy.triggers?.[id]}
                        onChange={(v) => updateTrigger(id, v)}
                        disabled={policySaving}
                      />
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
          <div className="admin-meta-line">
            {pinCount} watched CVEs · {snoozeCount} snoozed CVEs
          </div>
          <div className="admin-action-bar">
            <div className="admin-filter-chips">
              {['all', 'pin', 'snooze'].map(s => (
                <button
                  key={s}
                  className={`filter-chip ${watchlistState === s ? 'active' : ''}`}
                  onClick={() => {
                    if (s === 'all') {
                      setWatchlistState('all')
                      return
                    }
                    setWatchlistState((prev) => toggleChipSelection(prev, s, 'all'))
                  }}
                >
                  {s === 'snooze' ? 'Snoozed' : s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <div className="admin-card">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>CVE ID</th>
                  <th>SEVERITY</th>
                  <th>
                    EPSS
                    <HelpTip text={DOMAIN_TERM_TIPS.epss} />
                  </th>
                  <th>
                    KEV
                    <HelpTip text={DOMAIN_TERM_TIPS.kev} />
                  </th>
                  <th>
                    STATE
                    <HelpTip text={DOMAIN_TERM_TIPS.watchlistState} />
                  </th>
                  <th>CREATED</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {watchlistError && (
                  <TableLoadError colSpan={7} error={watchlistError} onRetry={loadWatchlist} compact />
                )}
                {watchlistRows === null && !watchlistError && (
                  <AdminTableBodySkeletonRows rows={5} cols={7} />
                )}
                {!watchlistError && watchlistRows?.length === 0 && <tr><td colSpan={7} className="admin-empty admin-empty--compact">{watchlistState === 'snooze' ? 'No snoozed CVEs (legacy entries only — snooze was removed from the analyst feed)' : watchlistState === 'pin' ? 'No pinned CVEs — pin CVEs from the main feed to track them here' : 'No watchlist entries yet — pin CVEs from the main feed to see them here'}</td></tr>}
                {!watchlistError && watchlistRows?.map(r => (
                  <tr key={r.cve_id}>
                    <td className="mono admin-table-id">{r.cve_id}</td>
                    <td>{r.severity || '—'}</td>
                    <td>{r.epss_score != null ? (r.epss_score * 100).toFixed(1) + '%' : '—'}</td>
                    <td>{r.is_kev ? <span className="badge badge-error">KEV</span> : ''}</td>
                    <td><span className={`badge ${r.state === 'pin' ? 'badge-info' : 'badge-warn'}`}>{r.state}</span></td>
                    <td className="admin-table-id">{fmtIso(r.created_at)}</td>
                    <td>
                      <button className="admin-btn admin-btn-danger admin-btn-compact"
                        onClick={() => removeWatchlist(r.cve_id)}>Remove</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!isAnalyst && snoozeCount > 0 && (
            <DangerZone title="Clear snoozes" subdued>
              <GuardedPurgePanel targets={[
                { target: 'watchlist_snoozes', title: 'Clear all snoozes', desc: 'Why: snoozed CVEs are hidden from the default watchlist view until you snooze again. What happens: removes every snooze entry. After: previously snoozed CVEs reappear in the default view; pinned CVEs are unaffected.', impact: `${snoozeCount} snoozed`, confirmWord: 'clear', run: clearSnoozes },
              ]} />
            </DangerZone>
          )}
        </div>
      )}

      {subtab === 'ioc' && (
        <div>
          <div className="admin-meta-line">
            {iocRows?.length ?? 0} entries
            {iocOldestAge ? ` · oldest ${fmtAge(iocOldestAge)}` : ''}
          </div>
          <div className="admin-filter-bar admin-filter-bar--fields">
            <Select
              className="admin-select"
              value={iocType}
              onChange={setIocType}
              options={[
                { value: '', label: 'All types' },
                { value: 'ip', label: 'IP' },
                { value: 'hash', label: 'Hash' },
                { value: 'domain', label: 'Domain' },
              ]}
            />
            <input className="admin-input" placeholder="Search value…" value={iocSearch} onChange={e => setIocSearch(e.target.value)} />
          </div>
          <div className="admin-card">
            <table className="admin-table">
              <thead><tr><th>VALUE</th><th>TYPE</th><th>CACHED AT</th><th>AGE</th><th></th></tr></thead>
              <tbody>
                {iocError && (
                  <TableLoadError colSpan={5} error={iocError} onRetry={loadIoc} compact />
                )}
                {iocRows === null && !iocError && <AdminTableBodySkeletonRows rows={5} cols={5} />}
                {!iocError && iocRows?.length === 0 && <tr><td colSpan={5} className="admin-empty admin-empty--compact">{iocType || iocSearch ? 'No IOC cache entries match the current filters' : 'IOC cache is empty — lookups populate it automatically as you search indicators from CVE details'}</td></tr>}
                {!iocError && iocRows?.map((r, i) => (
                  <tr key={i}>
                    <td className="mono admin-table-ellipsis">{r.value}</td>
                    <td>{r.ioc_type}</td>
                    <td className="admin-table-id">{fmtIso(r.cached_at)}</td>
                    <td>{fmtAge(r.age_seconds)}</td>
                    <td>
                      <button className="admin-btn admin-btn-danger admin-btn-compact"
                        onClick={() => deleteIoc(r.value)}>Clear</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(iocRows?.length ?? 0) > 0 && (
            <DangerZone title="Clear IOC cache" subdued>
              <GuardedPurgePanel targets={[
                { target: 'ioc_cache_all', title: 'Clear all IOC cache entries', desc: 'Why: IOC lookups are cached to avoid re-querying external threat-intel APIs on every page load. What happens: deletes every cached result below. After: the next lookup for each IOC is slower (re-fetches from the source API), but nothing is lost — the cache rebuilds itself automatically.', impact: `${iocRows?.length ?? 0} entries`, confirmWord: 'clear', run: clearAllIoc },
              ]} />
            </DangerZone>
          )}
        </div>
      )}

      {subtab === 'hunt' && (
        <div>
          <div className="admin-meta-line">
            {huntRows?.length ?? 0} packs
          </div>
          <div className="admin-filter-bar">
            <input className="admin-input" placeholder="Filter by technique ID…" value={huntTechnique} onChange={e => setHuntTechnique(e.target.value)} />
          </div>
          <div className="admin-card">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>PACK ID</th>
                  <th>
                    TECHNIQUE
                    <HelpTip text={DOMAIN_TERM_TIPS.huntTechnique} />
                  </th>
                  <th>CVE</th>
                  <th>
                    PRIORITY
                    <HelpTip text={DOMAIN_TERM_TIPS.huntPriority} />
                  </th>
                  <th>CREATED</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {huntError && (
                  <TableLoadError colSpan={6} error={huntError} onRetry={loadHunts} />
                )}
                {huntRows === null && !huntError && <AdminTableBodySkeletonRows rows={5} cols={6} />}
                {!huntError && huntRows?.length === 0 && <tr><td colSpan={6} className="admin-empty">{huntTechnique ? 'No hunt packs match that technique ID' : 'No hunt packs yet — these are created when you run a technique-based threat hunt from a CVE detail page'}</td></tr>}
                {!huntError && huntRows?.map(r => (
                  <tr key={r.id}>
                    <td>{r.id}</td>
                    <td className="mono admin-table-id">{r.technique_id}</td>
                    <td className="mono admin-table-id">{r.cve_id}</td>
                    <td>{r.priority}</td>
                    <td className="admin-table-id">{fmtIso(r.created_at)}</td>
                    <td>
                      <button className="admin-btn admin-btn-danger admin-btn-compact"
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