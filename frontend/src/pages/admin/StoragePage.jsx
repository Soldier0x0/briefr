import { useState, useEffect, useCallback } from 'react'
import { adminApi } from '../../api.js'
import ConfirmModal from './shared/ConfirmModal.jsx'
import AsyncSection from './shared/AsyncSection.jsx'
import { fmtBytes, diskPct, diskBarColor } from './formatters.js'

export default function StoragePage({ toast }) {
  const [storage, setStorage] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [confirm, setConfirm] = useState(null) // {target, word, extra}

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
    { target: 'epss_history_old', title: 'Prune EPSS history (>90 days)', desc: 'Deletes epss_history rows older than 90 days.', confirmWord: 'prune', impact: '~' + (storage?.tables?.epss_history ?? '?') + ' total rows' },
    { target: 'change_history_old', title: 'Prune change history (>90 days)', desc: 'Deletes cve_change_history rows older than 90 days.', confirmWord: 'prune', impact: `${storage?.tables?.cve_change_history ?? 0} total rows` },
    { target: 'rejected_cves', title: 'Remove rejected CVEs', desc: "Removes CVEs with 'Rejected reason:' in description.", confirmWord: 'purge', impact: 'varies' },
    { target: 'epss_backfill_reset', title: 'Re-trigger EPSS backfill', desc: 'Clears the epss_backfill_done marker. Next startup re-runs full backfill.', confirmWord: null, impact: 'not destructive' },
    { target: 'nvd_watermark', title: 'NVD backfill reset', desc: 'Clears the NVD sync watermark. Next NVD sync re-fetches from NVD_DAYS_BACK days ago.', confirmWord: 'backfill', impact: 'triggers full re-ingest', extraDaysBack: true },
  ]

  return (
    <div>
      {confirm && (
        <ConfirmModal
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

      <AsyncSection data={storage} error={loadError} onRetry={load}>
        {() => (
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
      </AsyncSection>

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
