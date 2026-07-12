import { useCallback, useEffect, useState } from 'react'
import AdminDataGrid from '../../pages/admin/shared/AdminDataGrid.jsx'
import ConfirmModal from '../ui/ConfirmModal.jsx'
import { deleteHuntPack, fetchHuntPacks } from '../../api.js'
import { notifyApiError } from '../Toast.jsx'
import { ingestLogUrl } from '../../utils/adminLinks.js'
import { SkeletonRows } from './shared.jsx'

const PRIORITIES = ['critical', 'high', 'medium', 'low']

function formatDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function downloadPack(pack) {
  // No hunt-pack-specific export path exists yet (PDF export is FR-3 scope —
  // forge-redesign.md §4/§5). Boring default for FR-2: reuse the existing
  // blob-download DOM pattern (utils/exportCsv.js downloadCsv) to dump the
  // pack's content as JSON — no new dependency, no invented PDF format.
  const payload = {
    id: pack.id,
    technique_id: pack.technique_id,
    cve_id: pack.cve_id,
    title: pack.title,
    priority: pack.priority,
    is_kev: pack.is_kev,
    sigma_yaml: pack.sigma_yaml,
    siem_queries: pack.siem_queries,
    log_patterns: pack.log_patterns,
    notes: pack.notes,
    created_at: pack.created_at,
    updated_at: pack.updated_at,
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `hunt-pack-${pack.technique_id}-${pack.cve_id}.json`
  link.rel = 'noopener'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  window.setTimeout(() => {
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }, 200)
}

/**
 * Hunt Pack Library (FR-2, forge-redesign.md §3.1): AdminDataGrid-style
 * table over the FR-1 list endpoint. Row click opens the pack in the
 * persistent Hunt Pack rail via onOpenPack.
 */
export default function LibraryView({ selectedPackId, onOpenPack, onPackDeleted }) {
  const [technique, setTechnique] = useState('')
  const [priority, setPriority] = useState('')
  const [kevOnly, setKevOnly] = useState(false)
  const [q, setQ] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)
  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    setErrorRequestId(null)
    return fetchHuntPacks({ techniqueId: technique.trim(), priority, q: q.trim(), limit: 200 })
      .then(setData)
      .catch(err => {
        setError(err.message || 'Failed to load hunt pack library')
        setErrorRequestId(err?.requestId || null)
        notifyApiError(err)
      })
      .finally(() => setLoading(false))
  }, [technique, priority, q])

  useEffect(() => {
    const handle = setTimeout(load, 250)
    return () => clearTimeout(handle)
  }, [load])

  const handleDeleteConfirm = useCallback(() => {
    if (!pendingDelete) return
    setDeleting(true)
    deleteHuntPack(pendingDelete.id)
      .then(() => {
        setPendingDelete(null)
        onPackDeleted?.(pendingDelete)
        return load()
      })
      .catch(err => notifyApiError(err))
      .finally(() => setDeleting(false))
  }, [pendingDelete, load, onPackDeleted])

  let packs = data?.packs || []
  if (kevOnly) packs = packs.filter(p => p.is_kev)

  const columns = [
    { id: 'technique_id', label: 'Technique', width: 90 },
    { id: 'cve_id', label: 'CVE', width: 130 },
    { id: 'title', label: 'Title' },
    {
      id: 'priority',
      label: 'Priority',
      width: 90,
      render: row => <span className={`fg-priority fg-priority-${row.priority} mono`}>{row.priority?.toUpperCase()}</span>,
    },
    {
      id: 'is_kev',
      label: 'KEV',
      width: 60,
      align: 'center',
      render: row => (row.is_kev ? <span className="fg-kev-badge mono">KEV</span> : '—'),
    },
    { id: 'created_at', label: 'Created', width: 150, render: row => formatDate(row.created_at) },
    { id: 'updated_at', label: 'Updated', width: 150, render: row => formatDate(row.updated_at) },
    {
      id: 'actions',
      label: 'Actions',
      width: 140,
      render: row => (
        <div className="fg-library-row-actions">
          <button
            type="button"
            className="fg-copy-btn mono"
            onClick={(e) => { e.stopPropagation(); downloadPack(row) }}
          >
            EXPORT
          </button>
          <button
            type="button"
            className="fg-backlog-dismiss mono"
            onClick={(e) => { e.stopPropagation(); setPendingDelete(row) }}
          >
            DELETE
          </button>
        </div>
      ),
    },
  ]

  return (
    <section className="fg-map fg-library" aria-label="Hunt pack library">
      <h2 className="fg-section-label mono">HUNT PACK LIBRARY</h2>

      <div className="fg-library-filters">
        <input
          type="text"
          className="fg-library-input mono"
          placeholder="Filter by technique (e.g. T1190)"
          value={technique}
          onChange={e => setTechnique(e.target.value)}
        />
        <select
          className="fg-library-select mono"
          value={priority}
          onChange={e => setPriority(e.target.value)}
        >
          <option value="">ALL PRIORITIES</option>
          {PRIORITIES.map(p => (
            <option key={p} value={p}>{p.toUpperCase()}</option>
          ))}
        </select>
        <label className="fg-stack-toggle mono">
          <input type="checkbox" checked={kevOnly} onChange={e => setKevOnly(e.target.checked)} />
          KEV ONLY
        </label>
        <input
          type="search"
          className="fg-library-input mono"
          placeholder="Search title…"
          value={q}
          onChange={e => setQ(e.target.value)}
        />
      </div>

      {error ? (
        <div className="fg-error-block">
          <p className="fg-error mono">
            // {error}
            {errorRequestId && (
              <>
                {' '}
                (<a href={ingestLogUrl({ level: 'ERROR', requestId: errorRequestId })}>
                  ref: {errorRequestId}
                </a>)
              </>
            )}
          </p>
          <button type="button" className="fg-error-retry-btn mono" onClick={load}>
            Retry
          </button>
        </div>
      ) : loading && !data ? (
        <SkeletonRows count={8} />
      ) : (
        <AdminDataGrid
          gridId="forge-hunt-pack-library"
          columns={columns}
          rows={packs}
          rowKey={row => row.id}
          onRowClick={row => onOpenPack?.(row.technique_id, row.id)}
          activeRowKey={selectedPackId ?? null}
          emptyMessage={
            technique || priority || kevOnly || q
              ? 'No saved hunt packs match these filters'
              : 'No saved hunt packs yet — generate one from Coverage, Scenarios, or Backlog'
          }
        />
      )}

      {pendingDelete && (
        <ConfirmModal
          title="Delete hunt pack?"
          message={`This permanently deletes "${pendingDelete.title}" (${pendingDelete.technique_id} / ${pendingDelete.cve_id}). Packs are regenerable from templates, so this is a hard delete — no undo.`}
          confirmLabel={deleting ? 'Deleting…' : 'Delete'}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setPendingDelete(null)}
        />
      )}

      {packs.length > 0 && (
        <p className="fg-library-hint mono">
          Click a row to open its technique in the Hunt Pack rail.
          {selectedPackId != null && ' · Currently open pack is highlighted.'}
        </p>
      )}
    </section>
  )
}
