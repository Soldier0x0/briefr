import { useCallback, useEffect, useMemo, useState } from 'react'
import { adminApi } from '../../api.js'
import { Select } from '../../components/ui/index.js'
import HelpTip from './shared/HelpTip.jsx'

const TIER_OPTIONS = [
  { value: 'free', label: 'Free tier (default)' },
  { value: 'premium_auto', label: 'Premium auto (relax when API key saved)' },
  { value: 'custom', label: 'Custom per-source overrides' },
]

export default function OutboundPacingPanel({ config, schema, onSaveKey, savingKeys }) {
  const [pacingMeta, setPacingMeta] = useState(null)
  const [overrides, setOverrides] = useState({})
  const [loadError, setLoadError] = useState(null)
  const [pacingLoading, setPacingLoading] = useState(true)

  const queue = config?.queue || {}
  const tier = queue.OUTBOUND_PACING_TIER || 'free'
  const tierField = useMemo(() => (schema || []).find(f => f.key === 'OUTBOUND_PACING_TIER'), [schema])
  const overridesField = useMemo(() => (schema || []).find(f => f.key === 'OUTBOUND_PACING_OVERRIDES'), [schema])

  const loadPacing = useCallback(async () => {
    setPacingLoading(true)
    try {
      const res = await adminApi.get('/outbound-pacing')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setPacingMeta(await res.json())
      setLoadError(null)
      const raw = queue.OUTBOUND_PACING_OVERRIDES
      if (raw) {
        try {
          const parsed = JSON.parse(raw)
          if (parsed && typeof parsed === 'object') setOverrides(parsed)
        } catch { /* ignore */ }
      }
    } catch (e) {
      setLoadError(e?.message || 'Pacing metadata unavailable')
    } finally {
      setPacingLoading(false)
    }
  }, [queue.OUTBOUND_PACING_OVERRIDES])

  useEffect(() => { loadPacing() }, [loadPacing])

  async function saveTier(value) {
    if (!tierField) return
    await onSaveKey('OUTBOUND_PACING_TIER', value, tierField)
    loadPacing()
  }

  async function saveOverrides() {
    if (!overridesField) return
    const ok = await onSaveKey('OUTBOUND_PACING_OVERRIDES', JSON.stringify(overrides), overridesField)
    if (ok) loadPacing()
  }

  const sources = pacingMeta?.sources || {}

  return (
    <div className="admin-card" style={{ marginBottom: 'var(--space-4)' }}>
      <div className="admin-card-title">
        Outbound API pacing
        <HelpTip text="Instance-wide minimum spacing between outbound HTTP calls. BRIEFR queues requests instead of dropping them." />
      </div>
      {pacingLoading && !pacingMeta && (
        <p className="metering-empty">Loading pacing metadata…</p>
      )}
      {loadError && <p className="metering-empty mono" style={{ color: 'var(--status-error)' }}>{loadError}</p>}
      {!pacingLoading && !loadError && pacingMeta && Object.keys(sources).length === 0 && (
        <p className="metering-empty">No outbound pacing sources configured.</p>
      )}
      <div className="config-grid" style={{ marginTop: '0.5rem' }}>
        <div className="config-row">
          <div className="config-row-label">
            <span className="admin-config-key">Pacing tier</span>
          </div>
          <Select
            className="admin-select"
            value={tier}
            onChange={saveTier}
            disabled={savingKeys?.has?.('OUTBOUND_PACING_TIER')}
            options={TIER_OPTIONS}
          />
        </div>
      </div>
      {tier === 'custom' && (
        <div style={{ marginTop: '0.75rem' }}>
          <table className="metering-table">
            <thead>
              <tr><th scope="col">Source</th><th scope="col">Default (s)</th><th scope="col">Override (s)</th></tr>
            </thead>
            <tbody>
              {Object.entries(sources).map(([key, meta]) => (
                <tr key={key}>
                  <td className="mono admin-config-value">{key}</td>
                  <td className="mono">{meta.min_interval_seconds}</td>
                  <td>
                    <input
                      className="admin-input"
                      type="number"
                      min={0}
                      step={0.1}
                      placeholder={String(meta.min_interval_seconds)}
                      value={overrides[key] ?? ''}
                      onChange={(e) => {
                        const v = e.target.value
                        setOverrides(prev => {
                          const next = { ...prev }
                          if (v === '') delete next[key]
                          else next[key] = Number(v)
                          return next
                        })
                      }}
                      style={{ maxWidth: '6rem' }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button type="button" className="admin-btn admin-btn-primary" style={{ marginTop: '0.5rem' }}
            disabled={savingKeys?.has?.('OUTBOUND_PACING_OVERRIDES')} onClick={saveOverrides}>
            Save overrides
          </button>
        </div>
      )}
    </div>
  )
}
