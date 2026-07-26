import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { adminApi } from '../../api.js'

export default function IntelSnapshotPanel({ toast }) {
  const [status, setStatus] = useState(null)
  const [inputPath, setInputPath] = useState('')
  const [mode, setMode] = useState('merge')
  const [loading, setLoading] = useState(false)

  const loadStatus = useCallback(async () => {
    try {
      const res = await adminApi.get('/intel-snapshot/status')
      setStatus(await res.json())
    } catch {
      setStatus(null)
    }
  }, [])

  useEffect(() => {
    loadStatus()
  }, [loadStatus])

  async function startImport() {
    if (!inputPath.trim()) {
      toast('Enter the server path to a .pgdump.gz bundle', false)
      return
    }
    setLoading(true)
    try {
      const res = await adminApi.post('/intel-snapshot/import', {
        input_path: inputPath.trim(),
        mode,
        confirm_text: 'import',
        replace_intel: mode === 'bootstrap',
      })
      const data = await res.json()
      toast(data.ok ? data.message : data.detail || 'Import failed', data.ok)
      loadStatus()
    } catch (e) {
      toast(String(e.message), false)
    }
    setLoading(false)
  }

  return (
    <section className="admin-section" style={{ marginBottom: '1.5rem' }}>
      <h2 className="admin-section-title">Intel snapshot</h2>
      <p className="admin-page-subtitle" style={{ marginTop: 0 }}>
        Import publishable CVE/correlation/embeddings data without touching operator settings
        (stack, API keys, IOC cache). CLI: <code>scripts/import_intel_snapshot.py --mode merge</code>.
        See <code>docs/INTEL_PUBLISH.md</code>.
      </p>

      {mode === 'bootstrap' && (
        <div className="admin-callout admin-callout-amber" style={{ marginBottom: '0.75rem' }}>
          <AlertTriangle size={16} strokeWidth={2} />
          <span>
            <strong>Bootstrap</strong> replaces intel tables and requires empty operator tables.
            Use <strong>merge</strong> on an existing instance with users and preferences.
          </span>
        </div>
      )}

      <div className="stat-card-row" style={{ marginBottom: '0.75rem' }}>
        <div className="stat-card">
          <div className="stat-card-label">LAST IMPORT</div>
          <div className="stat-card-value">{status?.last_import_at || '—'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-label">MODE</div>
          <div className="stat-card-value">{status?.last_import_mode || '—'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-label">BUNDLE EXPORTED</div>
          <div className="stat-card-value">{status?.last_manifest_exported_at || '—'}</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center', marginBottom: '0.75rem' }}>
        <button
          type="button"
          className={`admin-btn ${mode === 'merge' ? 'admin-btn-primary' : 'admin-btn-ghost'}`}
          onClick={() => setMode('merge')}
        >
          Merge (keep app data)
        </button>
        <button
          type="button"
          className={`admin-btn ${mode === 'bootstrap' ? 'admin-btn-primary' : 'admin-btn-ghost'}`}
          onClick={() => setMode('bootstrap')}
        >
          Bootstrap (empty operator tables)
        </button>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          className="admin-input"
          style={{ minWidth: 320, fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}
          placeholder="/var/lib/briefr/intel-publish/briefr-intel-2026-07-26.pgdump.gz"
          value={inputPath}
          onChange={(e) => setInputPath(e.target.value)}
          aria-label="Bundle path on server"
        />
        <button
          type="button"
          className="admin-btn admin-btn-primary"
          onClick={startImport}
          disabled={loading}
        >
          {loading ? 'Starting…' : 'Import snapshot'}
        </button>
      </div>
    </section>
  )
}
