import { useState, useEffect, useCallback, useMemo } from 'react'
import { adminApi } from '../../api.js'
import AsyncSection from './shared/AsyncSection.jsx'
import DangerZone from './shared/DangerZone.jsx'
import GuardedPurgePanel from './shared/GuardedPurgePanel.jsx'
import AdminDataGrid from './shared/AdminDataGrid.jsx'
import { fmtBytes, diskPct, diskBarColor } from './formatters.js'

const TABLE_SIZE_COLUMNS = [
  { id: 'table', label: 'Table', width: 220 },
  { id: 'size_bytes', label: 'Size', width: 120, render: (row) => fmtBytes(row.size_bytes) },
  { id: 'rows', label: 'Rows', width: 100, render: (row) => (
    row.rows >= 0 ? row.rows.toLocaleString() : '—'
  ) },
]

export default function StoragePage({ toast }) {
  const [storage, setStorage] = useState(null)
  const [loadError, setLoadError] = useState(null)

  const load = useCallback(async () => {
    try {
      const res = await adminApi.get('/storage')
      setStorage(await res.json())
      setLoadError(null)
    } catch (e) {
      setLoadError(e)
    }
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

  const dbPartition = storage?.db_partition || {}
  const backupPartition = storage?.backup_partition || {}
  const dbPct = diskPct(dbPartition)
  const backupPct = diskPct(backupPartition)

  const tableSizeRows = useMemo(() => {
    const counts = storage?.tables || {}
    return (storage?.table_sizes || []).map((row) => ({
      ...row,
      rows: counts[row.table] ?? -1,
    }))
  }, [storage])

  const growth = storage?.growth_estimate
  const diskIo = storage?.disk_io

  const purgeCards = [
    { target: 'ioc_cache', title: 'Clear IOC cache', desc: 'Why: IOC lookups (IPs, hashes, domains) are cached to avoid re-querying external threat-intel APIs on every page load. What happens: deletes every cached result. After: the next lookup for each IOC is slower (re-fetches from the source API), but nothing is lost — the cache rebuilds itself automatically.', confirmWord: 'clear', impact: `${storage?.tables?.ioc_cache ?? 0} rows`, run: () => doPurge('ioc_cache', 'clear') },
    { target: 'feed_cache', title: 'Clear feed cache', desc: 'Why: the incident/news feed is cached so the dashboard loads instantly. What happens: deletes the cached feed snapshot. After: the next incident feed load rebuilds it from scratch and will be noticeably slower once.', confirmWord: 'clear', impact: `${storage?.tables?.feed_cache ?? 0} rows`, run: () => doPurge('feed_cache', 'clear') },
    { target: 'epss_history_old', title: 'Prune EPSS history (>90 days)', desc: 'Why: EPSS scores are tracked over time to show trend charts, but old history is rarely useful and takes up space. What happens: deletes EPSS history rows older than 90 days. After: trend charts only show the last 90 days; current EPSS scores are unaffected.', confirmWord: 'prune', impact: '~' + (storage?.tables?.epss_history ?? '?') + ' total rows', run: () => doPurge('epss_history_old', 'prune') },
    { target: 'change_history_old', title: 'Prune change history (>90 days)', desc: 'Why: every CVE field change is logged for audit/diff purposes; old entries add up. What happens: deletes change-history rows older than 90 days. After: you lose the ability to see what changed on a CVE before that window; current CVE data is unaffected.', confirmWord: 'prune', impact: `${storage?.tables?.cve_change_history ?? 0} total rows`, run: () => doPurge('change_history_old', 'prune') },
    { target: 'rejected_cves', title: 'Remove rejected CVEs', desc: "Why: NVD occasionally marks a CVE ID as rejected/withdrawn; we keep a placeholder so it doesn't look missing, but they clutter search. What happens: deletes CVEs whose description starts with 'Rejected reason:'. After: those IDs disappear from search until/unless NVD re-publishes them.", confirmWord: 'purge', impact: 'varies', run: () => doPurge('rejected_cves', 'purge') },
    { target: 'epss_backfill_reset', title: 'Re-trigger EPSS backfill', desc: 'Why: use this if EPSS scores look incomplete or stale across many CVEs. What happens: clears the internal marker that says backfill already ran. After: the next startup re-downloads the full EPSS dataset — not destructive, nothing is deleted.', confirmWord: null, impact: 'not destructive', actionLabel: 'Reset', run: () => doPurge('epss_backfill_reset', '') },
    { target: 'nvd_watermark', title: 'NVD backfill reset', desc: 'Why: use this if NVD sync seems to have missed CVEs (e.g. after downtime). What happens: clears the watermark that tracks how far back NVD sync has already fetched. After: the next NVD sync re-fetches everything from NVD_DAYS_BACK days ago, which can take a while and re-uses NVD API quota.', confirmWord: 'backfill', impact: 'triggers full re-ingest', extraDaysBack: true, run: (daysBack) => doPurge('nvd_watermark', 'backfill', daysBack ? { days_back: daysBack } : {}) },
  ]

  return (
    <div>
      <h1 className="admin-page-title">Storage</h1>
      <p className="admin-page-subtitle">Disk usage, table sizes, and cache/log purge tools. Purges are destructive and cannot be undone.</p>

      <AsyncSection data={storage} error={loadError} onRetry={load}>
        {() => (
          <>
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
                    Database: {storage.db_path} ({fmtBytes(storage.db_size_bytes)})
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

            <div className="admin-card" style={{ marginTop: '1rem' }}>
              <div className="admin-card-title">Table sizes</div>
              {growth?.bytes_per_day != null && (
                <p style={{ fontSize: '0.75rem', color: 'var(--text3)', marginBottom: '0.5rem' }}>
                  Estimated growth: ~{fmtBytes(growth.bytes_per_day)}/day
                  {growth.sample_days ? ` (from ${growth.sample_days}d backup trend)` : ''}
                </p>
              )}
              {growth?.bytes_per_day == null && growth?.basis && (
                <p style={{ fontSize: '0.75rem', color: 'var(--text3)', marginBottom: '0.5rem' }}>
                  Growth estimate unavailable ({growth.basis.replace(/_/g, ' ')}).
                </p>
              )}
              <AdminDataGrid
                gridId="storage-table-sizes"
                columns={TABLE_SIZE_COLUMNS}
                rows={tableSizeRows}
                rowKey={(row) => row.table}
                emptyMessage="No table size data"
              />
            </div>

            {diskIo?.available && (
              <div className="admin-card" style={{ marginTop: '1rem' }}>
                <div className="admin-card-title">Host disk I/O</div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text3)', marginBottom: '0.5rem' }}>
                  Cumulative reads/writes since boot for device <code>{diskIo.device}</code>.
                </p>
                <div className="admin-two-col" style={{ gap: '1rem' }}>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text2)' }}>
                    Reads: {diskIo.reads_completed?.toLocaleString()} ({fmtBytes(diskIo.read_bytes)})
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text2)' }}>
                    Writes: {diskIo.writes_completed?.toLocaleString()} ({fmtBytes(diskIo.write_bytes)})
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </AsyncSection>

      <DangerZone title="Purge controls" subdued>
        <details className="admin-collapse">
          <summary style={{ cursor: 'pointer', fontSize: '0.8125rem', color: 'var(--text2)', marginBottom: '0.5rem' }}>
            Expand purge targets ({purgeCards.length})
          </summary>
          <p style={{ fontSize: '0.75rem', color: 'var(--text3)', marginTop: '0.25rem', marginBottom: '0.75rem' }}>
            Pick what to clear, read what it does, then type &quot;clear&quot; to enable the button.
          </p>
          <GuardedPurgePanel targets={purgeCards} />
        </details>
      </DangerZone>
    </div>
  )
}
