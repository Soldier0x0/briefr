import { useState, useEffect, useCallback } from 'react'
import { adminApi } from '../../api.js'
import HelpTip from './shared/HelpTip.jsx'
import { fmtIso } from './formatters.js'
import { AdminTableBodySkeletonRows } from './shared/AdminSkeletons.jsx'
import StatCard from '../../components/ui/StatCard.jsx'
import Select from '../../components/ui/Select.jsx'

const CLASSIFICATION_LABELS = [
  { value: 'LEGITIMATE_DOMAIN', label: 'Legitimate domain' },
  { value: 'SHARED_LEGITIMATE_INFRASTRUCTURE', label: 'Shared legitimate infra' },
  { value: 'TRUSTED_SERVICE', label: 'Trusted service' },
  { value: 'UNKNOWN', label: 'Unknown' },
]

const emptyForm = { host: '', classification: 'SHARED_LEGITIMATE_INFRASTRUCTURE', enabled: 1, reason: '', notes: '' }

export default function ThreatIntelPage({ toast }) {
  const [status, setStatus] = useState(null)
  const [rows, setRows] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)

  const loadStatus = useCallback(async () => {
    try {
      const res = await adminApi.get('/threat-intel/status')
      if (res.ok) setStatus(await res.json())
    } catch { /* status is best-effort */ }
  }, [])

  const loadRows = useCallback(async () => {
    try {
      const res = await adminApi.get('/infra-classifications')
      const data = await res.json()
      setRows(data.data || [])
    } catch { setRows([]) }
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

  function startEdit(row) {
    setEditingId(row.id)
    setForm({
      host: row.host,
      classification: row.classification,
      enabled: row.enabled,
      reason: row.reason || '',
      notes: row.notes || '',
    })
  }

  async function toggleEnabled(row) {
    try {
      await adminApi.patchJson(`/infra-classifications/${row.id}`, { enabled: row.enabled ? 0 : 1 })
      toast(row.enabled ? 'Classification disabled' : 'Classification enabled', true)
      loadRows()
    } catch (err) { toast(String(err.message || 'Failed to update'), false) }
  }

  async function remove(row) {
    try {
      await adminApi.del(`/infra-classifications/${row.id}`)
      toast(`Removed ${row.host}`, true)
      loadRows()
      loadStatus()
    } catch (err) { toast(String(err.message || 'Failed to remove'), false) }
  }

  const eligibleCount = status?.eligible_count ?? '—'
  const excludedCount = status?.excluded_count ?? '—'
  const tokenState = status?.token_configured ? 'Configured' : 'Not set (503)'

  return (
    <div>
      <h1 className="admin-page-title">Threat-intel blocklist</h1>
      <p className="admin-page-subtitle">
        Malicious-domain candidates exported to DNS-blocklist operators. Exact IOC evidence is never deleted;
        infrastructure classification only controls host-level corroboration and export eligibility.
      </p>

      <div className="stat-card-row">
        <StatCard
          label="Publish"
          value={<span className={`badge ${status?.token_configured ? 'badge-info' : 'badge-warn'}`}>{tokenState}</span>}
          subLabel={<code>/api/threat-intel/blocklist.txt</code>}
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
      <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.4rem' }}>
        <a className="admin-btn" href="/api/threat-intel/blocklist.txt">Download TXT</a>
        <a className="admin-btn" href="/api/threat-intel/blocklist.json">Download JSON</a>
      </div>

      <div className="admin-card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ margin: '0 0 0.5rem' }}>
          {editingId ? 'Edit classification' : 'Add infrastructure classification'}
          <HelpTip text="Classified hosts are excluded from the malicious-domain export and from host-level corroboration. Exact-path IOC evidence (e.g. https://drive.google.com/uc?…) is never deleted." />
        </h3>
        <form onSubmit={submit} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.5rem' }}>
          <input className="admin-input" placeholder="host (e.g. drive.google.com)" value={form.host} onChange={e => setForm({ ...form, host: e.target.value })} required />
          <Select
            className="admin-select"
            value={form.classification}
            onValueChange={v => setForm({ ...form, classification: v })}
            options={CLASSIFICATION_LABELS}
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem' }}>
            <input type="checkbox" checked={Boolean(form.enabled)} onChange={e => setForm({ ...form, enabled: e.target.checked ? 1 : 0 })} />
            enabled
          </label>
          <input className="admin-input" placeholder="reason" value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} />
          <input className="admin-input" placeholder="notes (optional)" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
          <button className="admin-btn admin-btn-primary" type="submit">{editingId ? 'Save' : 'Add'}</button>
          {editingId && (
            <button className="admin-btn" type="button" onClick={() => { setEditingId(null); setForm(emptyForm) }}>Cancel</button>
          )}
        </form>
      </div>

      <div className="admin-card">
        <table className="admin-table">
          <thead>
            <tr>
              <th>HOST</th>
              <th>CLASSIFICATION</th>
              <th>STATE</th>
              <th>PROVENANCE</th>
              <th>REASON</th>
              <th>UPDATED</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows === null && <AdminTableBodySkeletonRows rows={5} cols={7} />}
            {rows?.length === 0 && <tr><td colSpan={7} className="admin-empty">No classifications yet — the curated seed (google.com, drive.google.com, t.me, …) is inserted on first boot.</td></tr>}
            {rows?.map(r => (
              <tr key={r.id}>
                <td className="mono" style={{ fontSize: '0.75rem' }}>{r.host}</td>
                <td><span className={`badge ${r.classification === 'LEGITIMATE_DOMAIN' ? 'badge-error' : r.classification === 'UNKNOWN' ? 'badge-warn' : 'badge-info'}`}>{r.classification}</span></td>
                <td>{r.enabled ? <span className="badge badge-ok">active</span> : <span className="badge badge-warn">disabled</span>}</td>
                <td style={{ fontSize: '0.75rem' }}>{r.provenance}</td>
                <td style={{ fontSize: '0.75rem', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.reason}</td>
                <td style={{ fontSize: '0.75rem' }}>{fmtIso(r.updated_at)}</td>
                <td>
                  <button className="admin-btn" style={{ fontSize: '0.7rem', padding: '0.1rem 0.35rem' }} onClick={() => startEdit(r)}>Edit</button>{' '}
                  <button className="admin-btn" style={{ fontSize: '0.7rem', padding: '0.1rem 0.35rem' }} onClick={() => toggleEnabled(r)}>{r.enabled ? 'Disable' : 'Enable'}</button>{' '}
                  <button className="admin-btn admin-btn-danger" style={{ fontSize: '0.7rem', padding: '0.1rem 0.35rem' }} onClick={() => remove(r)}>Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
