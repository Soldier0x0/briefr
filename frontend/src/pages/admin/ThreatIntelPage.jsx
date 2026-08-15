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
  const [downloading, setDownloading] = useState(null)

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

  async function downloadBlocklist(fmt) {
    if (downloading) return
    setDownloading(fmt)
    try {
      const res = await adminApi.get(`/threat-intel/blocklist.${fmt}`)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        toast(String(data.detail || `Download failed (${res.status})`), false)
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `briefr-blocklist.${fmt}`
      a.click()
      URL.revokeObjectURL(url)
      toast(`Blocklist downloaded (.${fmt})`, true)
    } catch (err) { toast(String(err.message || 'Download failed'), false) }
    finally { setDownloading(null) }
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

  const tokenState = status?.token_configured ? 'Configured' : 'Not set (503)'
  const eligibleCount = status?.eligible_count ?? '—'
  const excludedCount = status?.excluded_count ?? '—'

  return (
    <div>
      <h1 className="admin-page-title">Threat-intel blocklist</h1>
      <p className="admin-page-subtitle">
        Malicious-domain candidates exported to DNS-blocklist operators. Exact IOC evidence is never deleted;
        infrastructure classification only controls host-level corroboration and export eligibility.
      </p>

      {statusError && (
        <div className="admin-callout admin-callout-red" role="alert">
          <span>Failed to load export status: {statusError}</span>
          <button type="button" className="admin-btn admin-btn-ghost" onClick={loadStatus}>Retry</button>
        </div>
      )}

      <div className="stat-card-row">
        <StatCard
          label="Publish"
          value={statusLoading && !status ? '—' : <span className={`badge ${status?.token_configured ? 'badge-info' : 'badge-warn'}`}>{tokenState}</span>}
          subLabel={<code>/api/admin/threat-intel/blocklist.txt</code>}
        />
        <StatCard
          label="Candidates"
          value={eligibleCount}
          colorClass={Number(eligibleCount) > 0 ? 'color-green' : undefined}
          subLabel="eligible domains"
        />
        <StatCard
          label="Excluded"
          value={excludedCount}
          colorClass={Number(excludedCount) > 0 ? 'color-amber' : undefined}
          subLabel="infrastructure / un-corroborated"
        />
        <StatCard
          label="Rate limit"
          value={status?.rate_limit_per_minute ?? '—'}
          subLabel="requests/min per client IP"
        />
        <StatCard
          label="Last build"
          value={status?.generated_at ? fmtIso(status.generated_at) : '—'}
          subLabel="blocklist regeneration"
        />
      </div>
      <div className="admin-download-row">
        <button type="button" className="admin-btn" disabled={Boolean(downloading)} onClick={() => downloadBlocklist('txt')}>
          {downloading === 'txt' ? 'Exporting…' : 'Download TXT'}
        </button>
        <button type="button" className="admin-btn" disabled={Boolean(downloading)} onClick={() => downloadBlocklist('json')}>
          {downloading === 'json' ? 'Exporting…' : 'Download JSON'}
        </button>
        <button type="button" className="admin-btn" disabled={Boolean(downloading)} onClick={() => downloadBlocklist('csv')}>
          {downloading === 'csv' ? 'Exporting…' : 'Download CSV'}
        </button>
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
