import { useEffect, useState } from 'react'
import { RotateCcw, Sparkles } from 'lucide-react'
import { adminApi } from '../../api.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { Card, CardTitle, Pill, PillGroup, Select } from '../../components/ui/index.js'
import ToggleSwitch from './shared/ToggleSwitch.jsx'
import {
  getDisplayPrefs,
  setDisplayPrefs,
  resetDisplayPrefs,
  POLL_INTERVAL_OPTIONS,
  DEFAULT_TYPOGRAPHY_PX,
} from '../../utils/displayPrefs.js'
import {
  clearTypographyPreview,
  normalizeTypographyPx,
  PX_OPTIONS,
  setTypographyPreview,
  TYPOGRAPHY_LABELS,
  TYPOGRAPHY_ROLES,
} from '../../utils/typographyPrefs.js'
import { applyDisplayPrefs } from '../../utils/displayPrefsCore.js'

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
    const next = normalizeTypographyPx({ ...typographyDraft, [role]: px })
    setTypographyDraft(next)
    setTypographyPreview(next)
    applyDisplayPrefs({ ...getDisplayPrefs(), typographyPx: next })
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

  async function saveInstanceUiVariant() {
    if (!isAdmin) return
    setSaving(true)
    setStatus('')
    try {
      const nextVariant = prefs.uiVariant === 'pitch' ? 'pitch' : 'default'
      const res = await adminApi.putJson('/display/ui-variant-default', {
        ui_variant: nextVariant,
      })
      const body = res.data || res
      setPrefs((prev) => ({
        ...prev,
        instanceUiVariantDefault: body.ui_variant || nextVariant,
      }))
      setStatus(`Saved ${nextVariant === 'default' ? 'newspaper' : 'showcase'} as the instance default for new users.`)
    } catch (e) {
      setStatus(e.message || 'Could not save instance UI default.')
    } finally {
      setSaving(false)
    }
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

      <Card>
        <CardTitle>Typography (px)</CardTitle>
        <p style={{ fontSize: 'var(--type-meta)', color: 'var(--text3)', margin: '0 0 0.75rem' }}>
          Set pixel sizes per text role. Changes preview live in this browser session; Save stores your profile; admins can also set the instance default for users who have not customized typography.
        </p>
        <div className="display-typography-grid">
          {TYPOGRAPHY_ROLES.map(role => (
            <div key={role} className="display-typography-row">
              <label className="display-typography-row-label" htmlFor={`typography-${role}`}>
                {TYPOGRAPHY_LABELS[role]}
              </label>
              <Select
                id={`typography-${role}`}
                className="display-typography-select"
                value={String(typographyDraft[role])}
                onValueChange={(val) => updateTypographyRole(role, Number(val))}
                options={PX_OPTIONS.map(px => ({
                  value: String(px),
                  label: `${px}px`,
                }))}
                aria-label={`${TYPOGRAPHY_LABELS[role]} size`}
              />
            </div>
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
            Reset to default
          </button>
        </div>
        {status ? (
          <p className="display-typography-status mono">{status}</p>
        ) : null}
      </Card>

      <Card>
        <CardTitle>Status refresh</CardTitle>
        <PillGroup>
          {POLL_INTERVAL_OPTIONS.map(opt => (
            <Pill
              key={opt}
              active={prefs.pollIntervalSeconds === opt}
              onClick={() => update('pollIntervalSeconds', opt)}
            >
              Every {opt}s
            </Pill>
          ))}
        </PillGroup>
        <p style={{ fontSize: '0.75rem', color: 'var(--text3)', margin: '0.4rem 0 0' }}>
          How often the status bar polls the backend for live system stats.
        </p>
      </Card>

      <Card>
        <CardTitle>Timestamps</CardTitle>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8125rem', color: 'var(--text2)' }}>
          <ToggleSwitch on={!!prefs.utcTime} onChange={v => update('utcTime', v)} />
          Show times in UTC instead of your browser's local time
        </label>
      </Card>

      <Card>
        <CardTitle>Notifications</CardTitle>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8125rem', color: 'var(--text2)' }}>
          <ToggleSwitch on={!!prefs.notificationSound} onChange={v => update('notificationSound', v)} />
          Play a short chime when new high-priority notifications arrive
        </label>
      </Card>

      <Card>
        <CardTitle>Visual style</CardTitle>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8125rem', color: 'var(--text2)' }}>
          <ToggleSwitch
            on={prefs.uiVariant === 'default'}
            onChange={(v) => update('uiVariant', v ? 'default' : 'pitch')}
          />
          Newspaper Style — dense terminal layout, original BRIEFR
        </label>
        <p style={{ fontSize: '0.75rem', color: 'var(--text3)', margin: '0.4rem 0 0' }}>
          Showcase card style is the default (rounded cards, calmer spacing). Turn on Newspaper Style to restore the classic analyst layout across BRIEF, FEED, admin, and wallboard.
        </p>
        {isAdmin ? (
          <div className="display-typography-actions" style={{ marginTop: '0.75rem' }}>
            <button
              type="button"
              className="admin-btn admin-btn-ghost"
              onClick={saveInstanceUiVariant}
              disabled={saving}
            >
              <Sparkles size={13} strokeWidth={2} aria-hidden="true" />
              Save {prefs.uiVariant === 'default' ? 'newspaper' : 'showcase'} as instance default
            </button>
          </div>
        ) : null}
        {prefs.instanceUiVariantDefault ? (
          <p className="display-typography-status mono" style={{ marginTop: '0.5rem' }}>
            Instance default: {prefs.instanceUiVariantDefault === 'default' ? 'newspaper' : 'showcase'}
          </p>
        ) : null}
      </Card>

      <Card>
        <CardTitle>Motion</CardTitle>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8125rem', color: 'var(--text2)' }}>
          <ToggleSwitch on={!!prefs.reduceMotion} onChange={v => update('reduceMotion', v)} />
          Reduce interface motion (disables toast, modal, and button animations)
        </label>
      </Card>

      <Card>
        <CardTitle>Tables</CardTitle>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8125rem', color: 'var(--text2)' }}>
          <ToggleSwitch on={!!prefs.showTechnicalIds} onChange={v => update('showTechnicalIds', v)} />
          Show technical job IDs in scheduler tables
        </label>
        <p style={{ fontSize: '0.75rem', color: 'var(--text3)', margin: '0.4rem 0 0' }}>
          Remembered across pages and sessions, instead of resetting every time you leave the Scheduler page.
        </p>
      </Card>

      <button className="admin-btn admin-btn-ghost" style={{ fontSize: '0.75rem' }} onClick={reset}>
        <RotateCcw size={13} strokeWidth={2} /> Reset to defaults
      </button>
    </div>
  )
}
