import { useEffect, useState } from 'react'
import { RotateCcw } from 'lucide-react'
import { adminApi } from '../../api.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { Slider } from '../../components/ui/index.js'
import ToggleSwitch from './shared/ToggleSwitch.jsx'
import {
  getDisplayPrefs,
  setDisplayPrefs,
  resetDisplayPrefs,
  FONT_SCALE_OPTIONS,
  DENSITY_OPTIONS,
  POLL_INTERVAL_OPTIONS,
  DEFAULT_TYPOGRAPHY_PX,
} from '../../utils/displayPrefs.js'
import {
  clearTypographyPreview,
  normalizeTypographyPx,
  PX_MIN,
  PX_MAX,
  setTypographyPreview,
  TYPOGRAPHY_LABELS,
  TYPOGRAPHY_ROLES,
} from '../../utils/typographyPrefs.js'
import { applyDisplayPrefs } from '../../utils/displayPrefsCore.js'

const FONT_LABELS = { xsmall: 'Extra small', small: 'Small', medium: 'Medium (default)', large: 'Large', xlarge: 'Extra large' }
const DENSITY_LABELS = { compact: 'Compact', comfortable: 'Comfortable (default)', spacious: 'Spacious' }

export default function DisplayPage() {
  const { user } = useAuth()
  const [prefs, setPrefs] = useState(getDisplayPrefs())
  const [typographyDraft, setTypographyDraft] = useState(
    () => normalizeTypographyPx(getDisplayPrefs().typographyPx),
  )
  const [status, setStatus] = useState('')
  const [saving, setSaving] = useState(false)
  const isAdmin = user?.role === 'admin'

  useEffect(() => {
    function sync() {
      const next = getDisplayPrefs()
      setPrefs(next)
      setTypographyDraft(normalizeTypographyPx(next.typographyPx))
    }
    window.addEventListener('briefr-preferences-loaded', sync)
    window.addEventListener('briefr-display-prefs-changed', sync)
    return () => {
      window.removeEventListener('briefr-preferences-loaded', sync)
      window.removeEventListener('briefr-display-prefs-changed', sync)
    }
  }, [])

  function update(key, value) {
    const next = { ...prefs, [key]: value }
    setPrefs(next)
    void setDisplayPrefs(next).catch(() => setPrefs(getDisplayPrefs()))
  }

  function updateTypographyRole(role, px) {
    setTypographyDraft(prev => normalizeTypographyPx({ ...prev, [role]: px }))
  }

  function applyTypography() {
    setTypographyPreview(typographyDraft)
    applyDisplayPrefs({ ...getDisplayPrefs(), typographyPx: typographyDraft })
    setStatus('Preview applied for this browser session.')
  }

  async function saveTypographyProfile() {
    setSaving(true)
    setStatus('')
    try {
      clearTypographyPreview()
      const next = { ...prefs, typographyPx: typographyDraft }
      await setDisplayPrefs(next)
      setPrefs(getDisplayPrefs())
      setStatus('Saved as your default typography profile.')
    } catch {
      setStatus('Could not save typography profile.')
    } finally {
      setSaving(false)
    }
  }

  async function saveInstanceTypography() {
    if (!isAdmin) return
    setSaving(true)
    setStatus('')
    try {
      const res = await adminApi.putJson('/display/typography-default', {
        typography_px: typographyDraft,
      })
      const body = res.data || res
      const saved = normalizeTypographyPx(body.typography_px || typographyDraft)
      setPrefs(prev => ({ ...prev, instanceTypographyDefault: saved }))
      setStatus('Saved as the instance default for new users.')
    } catch (e) {
      setStatus(e.message || 'Could not save instance default.')
    } finally {
      setSaving(false)
    }
  }

  function resetTypographyDraft() {
    setTypographyDraft({ ...DEFAULT_TYPOGRAPHY_PX })
  }

  function reset() {
    clearTypographyPreview()
    void resetDisplayPrefs().finally(() => {
      const next = getDisplayPrefs()
      setPrefs(next)
      setTypographyDraft(normalizeTypographyPx(next.typographyPx))
    })
  }

  return (
    <div>
      <h1 className="admin-page-title">Display</h1>
      <p className="admin-page-subtitle">Display preferences saved to your account when signed in — synced across devices on this instance.</p>

      <div className="admin-card">
        <div className="admin-card-title">Typography (px)</div>
        <p style={{ fontSize: 'var(--type-meta)', color: 'var(--text3)', margin: '0 0 0.75rem' }}>
          Set pixel sizes per text role. Apply previews in this browser session; Save stores your profile; admins can also set the instance default for users who have not customized typography.
        </p>
        <div className="display-typography-grid">
          {TYPOGRAPHY_ROLES.map(role => (
            <Slider
              key={role}
              label={TYPOGRAPHY_LABELS[role]}
              value={typographyDraft[role]}
              min={PX_MIN}
              max={PX_MAX}
              step={1}
              valueSuffix="px"
              onChange={px => updateTypographyRole(role, px)}
            />
          ))}
        </div>
        <div className="display-typography-actions">
          <button type="button" className="admin-btn admin-btn-ghost" onClick={applyTypography} disabled={saving}>
            Apply
          </button>
          <button type="button" className="admin-btn" onClick={saveTypographyProfile} disabled={saving}>
            Save as my default
          </button>
          {isAdmin ? (
            <button type="button" className="admin-btn admin-btn-ghost" onClick={saveInstanceTypography} disabled={saving}>
              Save as instance default
            </button>
          ) : null}
          <button type="button" className="admin-btn admin-btn-ghost" onClick={resetTypographyDraft} disabled={saving}>
            Reset draft
          </button>
        </div>
        {status ? (
          <p className="display-typography-status mono">{status}</p>
        ) : null}
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Font size</div>
        <div className="admin-filter-chips">
          {FONT_SCALE_OPTIONS.map(opt => (
            <button
              key={opt}
              className={`filter-chip ${prefs.fontScale === opt ? 'active' : ''}`}
              onClick={() => update('fontScale', opt)}
            >
              {FONT_LABELS[opt]}
            </button>
          ))}
        </div>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Density</div>
        <div className="admin-filter-chips">
          {DENSITY_OPTIONS.map(opt => (
            <button
              key={opt}
              className={`filter-chip ${prefs.density === opt ? 'active' : ''}`}
              onClick={() => update('density', opt)}
            >
              {DENSITY_LABELS[opt]}
            </button>
          ))}
        </div>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Status refresh</div>
        <div className="admin-filter-chips">
          {POLL_INTERVAL_OPTIONS.map(opt => (
            <button
              key={opt}
              className={`filter-chip ${prefs.pollIntervalSeconds === opt ? 'active' : ''}`}
              onClick={() => update('pollIntervalSeconds', opt)}
            >
              Every {opt}s
            </button>
          ))}
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--text3)', margin: '0.4rem 0 0' }}>
          How often the status bar polls the backend for live system stats.
        </p>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Timestamps</div>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8125rem', color: 'var(--text2)' }}>
          <ToggleSwitch on={!!prefs.utcTime} onChange={v => update('utcTime', v)} />
          Show times in UTC instead of your browser's local time
        </label>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Notifications</div>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8125rem', color: 'var(--text2)' }}>
          <ToggleSwitch on={!!prefs.notificationSound} onChange={v => update('notificationSound', v)} />
          Play a short chime when new high-priority notifications arrive
        </label>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Motion</div>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8125rem', color: 'var(--text2)' }}>
          <ToggleSwitch on={!!prefs.reduceMotion} onChange={v => update('reduceMotion', v)} />
          Reduce interface motion (disables toast, modal, and button animations)
        </label>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Tables</div>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8125rem', color: 'var(--text2)' }}>
          <ToggleSwitch on={!!prefs.showTechnicalIds} onChange={v => update('showTechnicalIds', v)} />
          Show technical job IDs in scheduler tables
        </label>
        <p style={{ fontSize: '0.75rem', color: 'var(--text3)', margin: '0.4rem 0 0' }}>
          Remembered across pages and sessions, instead of resetting every time you leave the Scheduler page.
        </p>
      </div>

      <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={reset}>
        <RotateCcw size={13} strokeWidth={2} /> Reset to defaults
      </button>
    </div>
  )
}
