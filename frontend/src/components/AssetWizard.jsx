import { useEffect, useRef, useState } from 'react'
import { Select } from './ui/index.js'
import {
  AI_PRODUCTS,
  APP_CATEGORIES,
  CRITICALITY_LEVELS,
  ENTERPRISE_PRODUCTS,
  INDUSTRY_SECTORS,
  INTERNET_FACING_OPTIONS,
  OS_SUGGESTIONS,
} from '../config/assetCatalog.js'
import { suggestStackCatalog } from '../api.js'
import { buildEmptyProfile, downloadProfileJson, parseProfileFile } from '../utils/assetProfileIo.js'
import './AssetWizard.css'

const CATEGORY_API = {
  'Web Server': 'web_server',
  Database: 'database',
  'Network Device': 'other',
  'Cloud Platform': 'other',
  'Security Tool': 'other',
  Container: 'other',
  Other: 'other',
}

const STEPS = ['Operating Systems', 'Applications', 'Environment', 'AI / ML (optional)']

function filterSuggestions(list, query) {
  const q = (query || '').toLowerCase().trim()
  if (!q) return list.slice(0, 8)
  return list.filter(item => {
    const name = typeof item === 'string' ? item : item.name
    return name.toLowerCase().includes(q)
  }).slice(0, 8)
}

export default function AssetWizard({ initialProfile, onComplete, onCancel }) {
  const [step, setStep] = useState(0)
  const [profile, setProfile] = useState(() => initialProfile || buildEmptyProfile())
  const [catalogHints, setCatalogHints] = useState([])
  const fileRef = useRef(null)
  const catalogQueryRef = useRef('')

  useEffect(() => {
    if (step !== 0 && step !== 1) {
      setCatalogHints([])
      return undefined
    }
    const rows = step === 0 ? (profile.operatingSystems || []) : (profile.applications || [])
    const active = rows.find((r) => (r.product || '').trim().length >= 3)
    const q = (active?.product || '').trim()
    catalogQueryRef.current = q
    if (q.length < 3) {
      setCatalogHints([])
      return undefined
    }
    const category = step === 0
      ? 'os'
      : (CATEGORY_API[active?.category] || undefined)
    let cancelled = false
    const t = setTimeout(() => {
      suggestStackCatalog(q, { limit: 8, category })
        .then((body) => {
          if (cancelled || catalogQueryRef.current !== q) return
          setCatalogHints(Array.isArray(body?.items) ? body.items : [])
        })
        .catch(() => {
          if (!cancelled) setCatalogHints([])
        })
    }, 180)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [step, profile.operatingSystems, profile.applications])

  function updateOs(idx, field, value) {
    setProfile(prev => {
      const list = [...(prev.operatingSystems || [])]
      list[idx] = { ...list[idx], [field]: value }
      return { ...prev, operatingSystems: list }
    })
  }

  function addOs() {
    setProfile(prev => ({
      ...prev,
      operatingSystems: [...(prev.operatingSystems || []), { product: '', version: '', vendor: '' }],
    }))
  }

  function removeOs(idx) {
    setProfile(prev => ({
      ...prev,
      operatingSystems: prev.operatingSystems.filter((_, i) => i !== idx),
    }))
  }

  function updateApp(idx, field, value) {
    setProfile(prev => {
      const list = [...(prev.applications || [])]
      list[idx] = { ...list[idx], [field]: value }
      return { ...prev, applications: list }
    })
  }

  function pickAppProduct(idx, entry) {
    setProfile(prev => {
      const list = [...(prev.applications || [])]
      list[idx] = {
        ...list[idx],
        product: entry.name,
        vendor: entry.vendor || '',
        cpeProduct: entry.product || '',
      }
      return { ...prev, applications: list }
    })
  }

  function addApp() {
    setProfile(prev => ({
      ...prev,
      applications: [
        ...(prev.applications || []),
        { category: 'Web Server', product: '', version: '', vendor: '' },
      ],
    }))
  }

  function removeApp(idx) {
    setProfile(prev => ({
      ...prev,
      applications: prev.applications.filter((_, i) => i !== idx),
    }))
  }

  function updateEnv(field, value) {
    setProfile(prev => ({
      ...prev,
      environment: { ...prev.environment, [field]: value },
    }))
  }

  function toggleAi(product) {
    setProfile(prev => {
      const list = [...(prev.aiSystems || [])]
      const idx = list.indexOf(product)
      if (idx >= 0) list.splice(idx, 1)
      else list.push(product)
      return { ...prev, aiSystems: list }
    })
  }

  function handleSaveFile() {
    downloadProfileJson(profile)
  }

  async function handleLoadFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const loaded = await parseProfileFile(file)
      setProfile(loaded)
    } catch {
      alert('Failed to load profile: Invalid or corrupted file.')
    }
    e.target.value = ''
  }

  function finish() {
    onComplete(profile)
  }

  return (
    <div className="asset-modal-overlay" role="presentation" onClick={onCancel}>
      <div
        className="asset-modal asset-wizard"
        role="dialog"
        aria-modal="true"
        onClick={e => e.stopPropagation()}
      >
        <div className="asset-wizard-head">
          <h2 className="asset-wizard-title mono">// ASSET PROFILE</h2>
          <p className="asset-wizard-step mono">
            Step {step + 1} of {STEPS.length} — {STEPS[step]}
          </p>
        </div>

        {step === 0 && (
          <div className="asset-wizard-body">
            {(profile.operatingSystems?.length ? profile.operatingSystems : [{ product: '', version: '' }]).map((os, idx) => (
              <div key={idx} className="asset-row">
                <input
                  className="asset-input mono"
                  placeholder="Product name"
                  value={os.product}
                  list={`os-suggest-${idx}`}
                  onChange={e => updateOs(idx, 'product', e.target.value)}
                />
                <datalist id={`os-suggest-${idx}`}>
                  {catalogHints.map((h) => (
                    <option key={`c-${h.vendor}-${h.product}`} value={h.display_name || h.product} />
                  ))}
                  {filterSuggestions(OS_SUGGESTIONS, os.product).map(s => (
                    <option key={s} value={s} />
                  ))}
                </datalist>
                <input
                  className="asset-input mono"
                  placeholder="Version"
                  value={os.version || ''}
                  onChange={e => updateOs(idx, 'version', e.target.value)}
                />
                <button type="button" className="asset-row-remove mono" onClick={() => removeOs(idx)}>−</button>
              </div>
            ))}
            <button type="button" className="asset-add mono" onClick={addOs}>+ Add OS</button>
          </div>
        )}

        {step === 1 && (
          <div className="asset-wizard-body">
            {(profile.applications?.length ? profile.applications : [{ category: 'Web Server', product: '', version: '' }]).map((app, idx) => (
              <div key={idx} className="asset-app-row">
                <Select
                  className="asset-select mono"
                  value={app.category || 'Other'}
                  onChange={(v) => updateApp(idx, 'category', v)}
                  options={APP_CATEGORIES.map(c => ({ value: c, label: c }))}
                />
                <input
                  className="asset-input mono"
                  placeholder="Product"
                  value={app.product}
                  list={`app-suggest-${idx}`}
                  onChange={e => updateApp(idx, 'product', e.target.value)}
                />
                <datalist id={`app-suggest-${idx}`}>
                  {catalogHints.map((h) => (
                    <option key={`c-${h.vendor}-${h.product}`} value={h.display_name || h.product} />
                  ))}
                  {filterSuggestions(ENTERPRISE_PRODUCTS, app.product).map(p => (
                    <option key={p.name} value={p.name} />
                  ))}
                </datalist>
                <input
                  className="asset-input mono"
                  placeholder="Version"
                  value={app.version || ''}
                  onChange={e => updateApp(idx, 'version', e.target.value)}
                />
                <button
                  type="button"
                  className="asset-row-remove mono"
                  onClick={() => {
                    const entry = ENTERPRISE_PRODUCTS.find(p => p.name === app.product)
                    if (entry) pickAppProduct(idx, entry)
                  }}
                  title="Apply vendor hint"
                >
                  ↵
                </button>
                <button type="button" className="asset-row-remove mono" onClick={() => removeApp(idx)}>−</button>
              </div>
            ))}
            <button type="button" className="asset-add mono" onClick={addApp}>+ Add application</button>
          </div>
        )}

        {step === 2 && (
          <div className="asset-wizard-body asset-env">
            <label className="asset-label mono">
              Internet-facing
              <Select
                className="asset-select mono"
                value={profile.environment?.internetFacing || 'Some'}
                onChange={(v) => updateEnv('internetFacing', v)}
                options={INTERNET_FACING_OPTIONS.map(o => ({ value: o, label: o }))}
              />
            </label>
            <label className="asset-label mono">
              Industry sector
              <Select
                className="asset-select mono"
                value={profile.environment?.industry || 'Technology'}
                onChange={(v) => updateEnv('industry', v)}
                options={INDUSTRY_SECTORS.map(s => ({ value: s, label: s }))}
              />
            </label>
            <label className="asset-label mono">
              Criticality
              <Select
                className="asset-select mono"
                value={profile.environment?.criticality || 'Medium'}
                onChange={(v) => updateEnv('criticality', v)}
                options={CRITICALITY_LEVELS.map(c => ({ value: c, label: c }))}
              />
            </label>
          </div>
        )}

        {step === 3 && (
          <div className="asset-wizard-body">
            <p className="asset-optional mono">// Optional — AI and ML systems in your environment</p>
            <div className="asset-ai-grid">
              {AI_PRODUCTS.map(name => {
                const on = (profile.aiSystems || []).includes(name)
                return (
                  <button
                    key={name}
                    type="button"
                    className={`asset-ai-chip mono${on ? ' asset-ai-chip--on' : ''}`}
                    onClick={() => toggleAi(name)}
                  >
                    {name}
                  </button>
                )
              })}
            </div>
            <div className="asset-file-actions">
              <button type="button" className="asset-btn mono" onClick={handleSaveFile}>Save profile to file</button>
              <button type="button" className="asset-btn mono" onClick={() => fileRef.current?.click()}>Load profile from file</button>
              <input ref={fileRef} type="file" accept="application/json,.json" className="session-lock-file" onChange={handleLoadFile} />
            </div>
          </div>
        )}

        <div className="asset-wizard-nav">
          {step > 0 && (
            <button type="button" className="asset-btn mono" onClick={() => setStep(s => s - 1)}>Back</button>
          )}
          <button type="button" className="asset-btn mono" onClick={onCancel}>Cancel</button>
          {step < STEPS.length - 1 ? (
            <button type="button" className="asset-btn asset-btn-primary mono" onClick={() => setStep(s => s + 1)}>Next</button>
          ) : (
            <button type="button" className="asset-btn asset-btn-primary mono" onClick={finish}>Apply profile</button>
          )}
        </div>
      </div>
    </div>
  )
}
