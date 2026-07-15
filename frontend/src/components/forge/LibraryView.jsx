import { useCallback, useEffect, useState } from 'react'
import { Checkbox, Select } from '../ui/index.js'
import AdminDataGrid from '../../pages/admin/shared/AdminDataGrid.jsx'
import ConfirmModal from '../ui/ConfirmModal.jsx'
import { deleteHuntPack, fetchHuntPacks } from '../../api.js'
import { notifyApiError } from '../Toast.jsx'
import { ingestLogUrl } from '../../utils/adminLinks.js'
import { SkeletonRows } from './shared.jsx'

const PRIORITIES = ['critical', 'high', 'medium', 'low']

function formatDate(value) {
  if (!value) return '—'
  // SQLite's default datetime() format ("YYYY-MM-DD HH:MM:SS") isn't
  // ISO 8601 — Safari's Date parser returns Invalid Date for the
  // space-separated form, unlike Chrome/Firefox. Normalize to "T".
  const normalized = typeof value === 'string' && value.includes(' ') && !value.includes('T')
    ? value.replace(' ', 'T')
    : value
  const d = new Date(normalized)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function exportPackPdf(pack, onError) {
  // FR-3 (forge-redesign.md §4/§5): pack export as PDF via the existing
  // jsPDF/exportCommon.js pattern — supersedes the FR-2 JSON-blob
  // placeholder now that PDF export is in scope. Library rows only know
  // technique_id (no loaded technique/case-study detail — that lives in the
  // Hunt Pack rail), so the PDF falls back to the bare technique_id line;
  // exporting the same pack from the rail includes technique name + tactic
  // and related case studies.
  return import('../../utils/huntPackPdf.js')
    .then(({ downloadHuntPackPdf }) => downloadHuntPackPdf(pack))
    .catch(err => {
      onError?.(err)
      throw err
    })
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
  const [exportingId, setExportingId] = useState(null)

  const load = useCallback((isActive = () => true) => {
    setLoading(true)
    setError(null)
    setErrorRequestId(null)
    return fetchHuntPacks({ techniqueId: technique.trim(), priority, q: q.trim(), limit: 200 })
      .then(payload => { if (isActive()) setData(payload) })
      .catch(err => {
        if (!isActive()) return
        setError(err.message || 'Failed to load hunt pack library')
        setErrorRequestId(err?.requestId || null)
        notifyApiError(err)
      })
      .finally(() => { if (isActive()) setLoading(false) })
  }, [technique, priority, q])

  useEffect(() => {
    let active = true
    const handle = setTimeout(() => load(() => active), 250)
    return () => { active = false; clearTimeout(handle) }
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
      render: row => (row.is_kev ? <span className="fg-kev-badge mono" title="CISA Known Exploited Vulnerabilities — confirmed active exploitation in the wild">KEV</span> : '—'),
    },
    {
      id: 'cwe_ids',
      label: 'CWE',
      width: 110,
      render: row => (row.cwe_ids?.length ? (
        <span title="MITRE Common Weakness Enumeration — the class of coding weakness behind the CVE">
          {row.cwe_ids.join(', ')}
        </span>
      ) : '—'),
    },
    {
      id: 'epss_score',
      label: 'EPSS',
      width: 80,
      render: row => (row.epss_score != null ? (
        <span title="FIRST.org Exploit Prediction Scoring System — probability of exploitation in the wild within 30 days">
          {`${(row.epss_score * 100).toFixed(1)}%`}
        </span>
      ) : '—'),
    },
    { id: 'created_at', label: 'Created', width: 150, render: row => formatDate(row.created_at) },
    { id: 'updated_at', label: 'Updated', width: 150, render: row => formatDate(row.updated_at) },
    {
      id: 'actions',
      label: 'Actions',
      width: 150,
      render: row => (
        <div className="fg-library-row-actions">
          <button
            type="button"
            className="fg-copy-btn mono"
            disabled={exportingId === row.id}
            onClick={(e) => {
              e.stopPropagation()
              setExportingId(row.id)
              exportPackPdf(row, err => notifyApiError(err))
                .catch(() => {})
                .finally(() => setExportingId(null))
            }}
          >
            {exportingId === row.id ? 'EXPORTING…' : 'EXPORT PDF'}
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
        <Select
          className="fg-library-select mono"
          value={priority}
          onChange={setPriority}
          options={[
            { value: '', label: 'ALL PRIORITIES' },
            ...PRIORITIES.map(p => ({ value: p, label: p.toUpperCase() })),
          ]}
        />
        <Checkbox
          id="forge-library-kev-only"
          checked={kevOnly}
          onCheckedChange={setKevOnly}
          label="KEV ONLY"
          className="fg-stack-toggle mono"
        />
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
