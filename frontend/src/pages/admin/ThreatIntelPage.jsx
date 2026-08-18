import { useState, useEffect, useCallback, useMemo } from 'react'
import { adminApi } from '../../api.js'
import HelpTip from './shared/HelpTip.jsx'
import { fmtIso } from './formatters.js'
import StatCard from '../../components/ui/StatCard.jsx'
import Select from '../../components/ui/Select.jsx'
import Checkbox from '../../components/ui/Checkbox.jsx'
import AsyncSection from './shared/AsyncSection.jsx'
import AdminDataGrid from './shared/AdminDataGrid.jsx'

const CLASSIFICATION_LABELS = [
  { value: 'LEGITIMATE_DOMAIN', label: 'Legitimate domain' },
  { value: 'SHARED_LEGITIMATE_INFRASTRUCTURE', label: 'Shared legitimate infra' },
  { value: 'TRUSTED_SERVICE', label: 'Trusted service' },
  { value: 'UNKNOWN', label: 'Unknown' },
]

const emptyForm = { host: '', classification: 'SHARED_LEGITIMATE_INFRASTRUCTURE', enabled: 1, reason: '', notes: '' }

const EMPTY_MESSAGE =
  'No classifications yet — the curated seed (google.com, drive.google.com, t.me, …) is inserted on first boot.'

export default function ThreatIntelPage({ toast }) {
  const [status, setStatus] = useState(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [statusError, setStatusError] = useState(null)
  const [rows, setRows] = useState(null)
  const [rowsLoading, setRowsLoading] = useState(true)
  const [rowsError, setRowsError] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)
  const [downloading, setDownloading] = useState(false)
  const [exportFormat, setExportFormat] = useState('csv')
  const [exportContent, setExportContent] = useState('domains')

  const FORMAT_OPTIONS = [
    { value: 'txt', label: 'TXT — one value per line' },
    { value: 'csv', label: 'CSV — spreadsheet columns' },
    { value: 'json', label: 'JSON — full audit trail' },
  ]

  const CONTENT_OPTIONS = [
    { value: 'domains', label: 'Domains only (minus genuine list)' },
    { value: 'urls', label: 'Exact URLs only' },
    { value: 'all', label: 'All eligible rows (CSV)' },
  ]

  const loadStatus = useCallback(async () => {
    setStatusLoading(true)
    setStatusError(null)
    try {
      const res = await adminApi.get('/threat-intel/status')
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setStatusError(String(data.detail || `HTTP ${res.status}`))
        return
      }
      setStatus(await res.json())
    } catch (err) {
      setStatusError(String(err.message || 'Failed to load status'))
    } finally {
      setStatusLoading(false)
    }
  }, [])

  const loadRows = useCallback(async () => {
    setRowsLoading(true)
    setRowsError(null)
    try {
      const res = await adminApi.get('/infra-classifications')
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setRowsError(String(data.detail || `HTTP ${res.status}`))
        return
      }
      const data = await res.json()
      setRows(data.data || [])
    } catch (err) {
      setRowsError(String(err.message || 'Failed to load classifications'))
    } finally {
      setRowsLoading(false)
    }
  }, [])

  useEffect(() => { loadStatus(); loadRows() }, [loadStatus, loadRows])

  async function submit(e) {
    e.preventDefault()
    try {
      const body = { ...form, host: form.host.trim().toLowerCase() }
      if (editingId) {
        await adminApi.patchJson(`/infra-classifications/${editingId}`, body)
        toast('Classification updated', true)
      } else {
        await adminApi.postJson('/infra-classifications', body)
        toast('Classification added', true)
      }
      setForm(emptyForm)
      setEditingId(null)
      loadRows()
      loadStatus()
    } catch (err) { toast(String(err.message || 'Failed to save classification'), false) }
  }

  const startEdit = useCallback((row) => {
    setEditingId(row.id)
    setForm({
      host: row.host,
      classification: row.classification,
      enabled: row.enabled,
      reason: row.reason || '',
      notes: row.notes || '',
    })
  }, [])

  const toggleEnabled = useCallback(async (row) => {
    try {
      await adminApi.patchJson(`/infra-classifications/${row.id}`, { enabled: row.enabled ? 0 : 1 })
      toast(row.enabled ? 'Classification disabled' : 'Classification enabled', true)
      loadRows()
    } catch (err) { toast(String(err.message || 'Failed to update'), false) }
  }, [loadRows, toast])

  const remove = useCallback(async (row) => {
    try {
      await adminApi.del(`/infra-classifications/${row.id}`)
      toast(`Removed ${row.host}`, true)
      loadRows()
      loadStatus()
    } catch (err) { toast(String(err.message || 'Failed to remove'), false) }
  }, [loadRows, loadStatus, toast])

  function effectiveContentMode(format, content) {
    if (format === 'json') return null
    if (format === 'txt' && content === 'all') return 'domains'
    return content
  }

  async function downloadBlocklist() {
    if (downloading) return
    const mode = effectiveContentMode(exportFormat, exportContent)
    if (exportFormat === 'txt' && exportContent === 'all') {
      toast('TXT export uses domains only — combined rows are CSV-only', true)
    }
    setDownloading(true)
    try {
      const modeParam = mode ? `?mode=${encodeURIComponent(mode)}` : ''
      const res = await adminApi.get(`/threat-intel/blocklist.${exportFormat}${modeParam}`)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        toast(String(data.detail || `Download failed (${res.status})`), false)
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const modeSuffix = mode ? `-${mode}` : ''
      a.download = `briefr-blocklist${modeSuffix}.${exportFormat}`
      a.click()
      URL.revokeObjectURL(url)
      toast(`Downloaded ${exportFormat.toUpperCase()} (${mode || 'full audit'})`, true)
    } catch (err) { toast(String(err.message || 'Download failed'), false) }
    finally { setDownloading(false) }
  }

  const classificationBadge = (classification) => (
    <span className={`badge ${classification === 'LEGITIMATE_DOMAIN' ? 'badge-error' : classification === 'UNKNOWN' ? 'badge-warn' : 'badge-info'}`}>
      {classification}
    </span>
  )

  const columns = useMemo(() => [
    {
      id: 'host',
      label: 'HOST',
      align: 'left',
      defaultVisible: true,
      minWidth: 180,
      render: (r) => <span className="mono admin-cell-sm">{r.host}</span>,
    },
    {
      id: 'classification',
      label: 'CLASSIFICATION',
      defaultVisible: true,
      width: 220,
      render: (r) => classificationBadge(r.classification),
    },
    {
      id: 'state',
      label: 'STATE',
      defaultVisible: true,
      width: 100,
      render: (r) => (r.enabled ? <span className="badge badge-ok">active</span> : <span className="badge badge-warn">disabled</span>),
    },
    {
      id: 'provenance',
      label: 'PROVENANCE',
      align: 'left',
      defaultVisible: true,
      width: 160,
      render: (r) => <span className="admin-cell-sm">{r.provenance}</span>,
    },
    {
      id: 'reason',
      label: 'REASON',
      align: 'left',
      defaultVisible: true,
      width: 260,
      render: (r) => <span className="admin-cell-sm">{r.reason}</span>,
    },
    {
      id: 'updated_at',
      label: 'UPDATED',
      align: 'left',
      defaultVisible: true,
      width: 160,
      render: (r) => <span className="admin-cell-sm">{fmtIso(r.updated_at)}</span>,
    },
    {
      id: 'actions',
      label: '',
      defaultVisible: true,
      width: 220,
      sortable: false,
      render: (r) => (
        <>
          <button className="admin-btn admin-btn-sm" onClick={() => startEdit(r)}>Edit</button>{' '}
          <button className="admin-btn admin-btn-sm" onClick={() => toggleEnabled(r)}>{r.enabled ? 'Disable' : 'Enable'}</button>{' '}
          <button className="admin-btn admin-btn-sm admin-btn-danger" onClick={() => remove(r)}>Remove</button>
        </>
      ),
    },
  ], [startEdit, toggleEnabled, remove])

  const domainExportCount = status?.eligible_domain_count ?? '—'
  const urlExportCount = status?.eligible_url_count ?? '—'
  const excludedCount = status?.excluded_count ?? '—'
  const genuineHostCount = status?.genuine_host_count ?? '—'

  const selectedFormat = FORMAT_OPTIONS.find((o) => o.value === exportFormat)
  const selectedContent = CONTENT_OPTIONS.find((o) => o.value === exportContent)

  return (
    <div>
      <h1 className="admin-page-title">Threat-intel blocklist</h1>
      <p className="admin-page-subtitle">
        Build malicious-domain and URL exports from ThreatFox, URLhaus, PhishTank, and
        corroborated OTX pulses. Genuine hosts (Tranco top-1M + curated seeds) are removed
        from <em>domain</em> export only — exact malicious URLs on shared infrastructure
        still export when you choose URL mode.
      </p>

      {statusError && (
        <div className="admin-callout admin-callout-red" role="alert">
          <span>Failed to load export status: {statusError}</span>
          <button type="button" className="admin-btn admin-btn-ghost" onClick={loadStatus}>Retry</button>
        </div>
      )}

      <div className="stat-card-row">
        <StatCard
          label="Domain export"
          value={domainExportCount}
          colorClass={Number(domainExportCount) > 0 ? 'color-green' : undefined}
          subLabel="eligible after genuine filter"
        />
        <StatCard
          label="URL export"
          value={urlExportCount}
          colorClass={Number(urlExportCount) > 0 ? 'color-green' : undefined}
          subLabel="exact malicious URIs"
        />
        <StatCard
          label="Genuine hosts"
          value={genuineHostCount}
          subLabel="Tranco + curated exclusions"
        />
        <StatCard
          label="Excluded"
          value={excludedCount}
          colorClass={Number(excludedCount) > 0 ? 'color-amber' : undefined}
          subLabel="un-corroborated / filtered"
        />
        <StatCard
          label="Last build"
          value={status?.generated_at ? fmtIso(status.generated_at) : '—'}
          subLabel="blocklist regeneration"
        />
      </div>

      <div className="admin-card admin-card-spaced">
        <h3 className="admin-card-title">
          Export blocklist
          <HelpTip text="Admin-only download — no public feed URL. Choose format (TXT/CSV/JSON) and content (domains vs exact URLs). Domain export subtracts the genuine-host list (Tranco + curated). URL export keeps full malicious paths even on shared hosts like drive.google.com." />
        </h3>
        <div className="admin-form-grid admin-form-grid-export">
          <label className="admin-field-label">
            Format
            <Select
              className="admin-select"
              value={exportFormat}
              onValueChange={setExportFormat}
              options={FORMAT_OPTIONS}
              aria-label="Export file format"
            />
          </label>
          <label className="admin-field-label">
            Content
            <Select
              className="admin-select"
              value={exportContent}
              onValueChange={setExportContent}
              options={CONTENT_OPTIONS}
              aria-label="Export content mode"
              disabled={exportFormat === 'json'}
            />
          </label>
          <button
            type="button"
            className="admin-btn admin-btn-primary"
            disabled={downloading}
            onClick={downloadBlocklist}
          >
            {downloading ? 'Exporting…' : 'Download export'}
          </button>
        </div>
        <p className="admin-page-subtitle">
          {selectedFormat?.label}: {selectedFormat?.value === 'json'
            ? 'includes eligible and excluded candidates with evidence.'
            : selectedContent?.label + ' — ' + (exportContent === 'domains'
              ? 'malicious domains minus genuine/Tranco hosts.'
              : exportContent === 'urls'
                ? 'full URLs; genuine list does not apply.'
                : 'domain and URL rows together (CSV only).')}
        </p>
      </div>

      <div className="admin-card admin-card-spaced">
        <h3 className="admin-card-title">
          {editingId ? 'Edit classification' : 'Add infrastructure classification'}
          <HelpTip text="Classified hosts are excluded from the malicious-domain export and from host-level corroboration. Exact-path IOC evidence (e.g. https://drive.google.com/uc?…) is never deleted. Add infra-classifications for hosts that are frequently flagged as false positives so they are excluded from export and do not generate corroboration noise. The 6 curated seed entries (google.com, microsoft.com, apple.com, drive.google.com, t.me, steamcommunity.com) are provided as a starting point — you may add, edit, or remove entries as needed for your environment." />
        </h3>
        <p className="admin-page-subtitle">
          Infrastructure classifications control whether a host appears in the blocklist export and whether it triggers host-level corroboration. Each entry consists of a canonical host, a classification (Legitimate domain / Shared legitimate infrastructure / Trusted service / Unknown), and an optional reason. Add entries for hosts that are frequently flagged as false positives so they are excluded from export and do not generate corroboration noise. The 6 curated seed entries (google.com, microsoft.com, apple.com, drive.google.com, t.me, steamcommunity.com) are provided as a starting point — you may add, edit, or remove entries as needed for your environment.
        </p>
        <form onSubmit={submit} className="admin-form-grid">
          <input className="admin-input" placeholder="host (e.g. drive.google.com)" value={form.host} onChange={e => setForm({ ...form, host: e.target.value })} required />
          <Select
            className="admin-select"
            value={form.classification}
            onValueChange={v => setForm({ ...form, classification: v })}
            options={CLASSIFICATION_LABELS}
          />
          <Checkbox
            id="classification-enabled"
            checked={Boolean(form.enabled)}
            onCheckedChange={checked => setForm({ ...form, enabled: checked ? 1 : 0 })}
            label="enabled"
            className="admin-checkbox-inline"
          />
          <input className="admin-input" placeholder="reason" value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} />
          <input className="admin-input" placeholder="notes (optional)" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
          <button className="admin-btn admin-btn-primary" type="submit">{editingId ? 'Save' : 'Add'}</button>
          {editingId && (
            <button className="admin-btn" type="button" onClick={() => { setEditingId(null); setForm(emptyForm) }}>Cancel</button>
          )}
        </form>
      </div>

      <div className="admin-card admin-card-spaced">
        <AsyncSection
          data={rowsLoading && !rows ? null : rows}
          error={rowsError}
          onRetry={loadRows}
          emptyMessage={EMPTY_MESSAGE}
        >
          {(rowData) => (
            <AdminDataGrid
              gridId="threat-intel-classifications"
              columns={columns}
              rows={rowData}
              rowKey={(r) => String(r.id)}
              emptyMessage={EMPTY_MESSAGE}
            />
          )}
        </AsyncSection>
      </div>
    </div>
  )
}
