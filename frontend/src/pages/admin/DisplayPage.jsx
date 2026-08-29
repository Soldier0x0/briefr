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
import {
  DEFAULT_NOTIFICATION_MUTES,
  NOTIFICATION_MUTE_CATEGORIES,
} from '../../utils/notificationInbox.js'

const NOTIFICATION_MUTE_LABELS = {
  watchlist: 'Watchlist (pinned CVE)',
  ioc_watchlist: 'IOC watchlist hit',
  job_error: 'Scheduler job failure',
  api_key_unhealthy: 'API key unhealthy',
  webhook_failure: 'Webhook delivery failure',
}

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
    void setDisplayPrefs(next).catch(() => {
      setPrefs(getDisplayPrefs())
      setStatus('Could not save display preferences.')
    })
  }

  function updateNotificationMute(category, muted) {
    const previous = prefs
    const merged = {
      ...DEFAULT_NOTIFICATION_MUTES,
      ...(prefs.notificationMutes || {}),
      [category]: muted,
    }
    const next = { ...prefs, notificationMutes: merged }
    setPrefs(next)
    setSaving(true)
    void setDisplayPrefs(next)
      .then(() => {
        setStatus('')
      })
      .catch(() => {
        setPrefs(previous)
        setStatus('Could not save notification mutes.')
      })
      .finally(() => setSaving(false))
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
        <p className="admin-pref-hint" style={{ margin: '0 0 var(--space-3)' }}>
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
          <p className={`display-typography-status mono${/could not/i.test(status) ? ' display-typography-status--error' : ''}`}>{status}</p>
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
        <p className="admin-pref-hint">
          How often the status bar polls the backend for live system stats.
        </p>
      </Card>

      <Card>
        <CardTitle>Preferences</CardTitle>
        <div className="admin-pref-row">
          <div className="admin-pref-copy">
            <div className="admin-pref-label">UTC timestamps</div>
            <p className="admin-pref-hint">Show times in UTC instead of your browser's local time.</p>
          </div>
          <ToggleSwitch on={!!prefs.utcTime} onChange={v => update('utcTime', v)} label="UTC timestamps" />
        </div>
        <div className="admin-pref-row">
          <div className="admin-pref-copy">
            <div className="admin-pref-label">Newspaper style</div>
            <p className="admin-pref-hint">
              Showcase card style is the default. Newspaper restores the dense terminal layout across BRIEF, FEED, admin, and wallboard.
            </p>
          </div>
          <ToggleSwitch
            on={prefs.uiVariant === 'default'}
            onChange={(v) => update('uiVariant', v ? 'default' : 'pitch')}
            label="Newspaper style"
          />
        </div>
        {isAdmin ? (
          <div className="display-typography-actions">
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
          <p className="display-typography-status mono">
            Instance default: {prefs.instanceUiVariantDefault === 'default' ? 'newspaper' : 'showcase'}
          </p>
        ) : null}
        <div className="admin-pref-row">
          <div className="admin-pref-copy">
            <div className="admin-pref-label">Reduce motion</div>
            <p className="admin-pref-hint">Disables toast, modal, and button animations.</p>
          </div>
          <ToggleSwitch on={!!prefs.reduceMotion} onChange={v => update('reduceMotion', v)} label="Reduce motion" />
        </div>
        <div className="admin-pref-row">
          <div className="admin-pref-copy">
            <div className="admin-pref-label">Technical job IDs</div>
            <p className="admin-pref-hint">Show technical job IDs in scheduler tables. Remembered across pages and sessions.</p>
          </div>
          <ToggleSwitch on={!!prefs.showTechnicalIds} onChange={v => update('showTechnicalIds', v)} label="Technical job IDs" />
        </div>
      </Card>

      <Card>
        <CardTitle>Notifications</CardTitle>
        <div className="admin-pref-row">
          <div className="admin-pref-copy">
            <div className="admin-pref-label">Notification chime</div>
            <p className="admin-pref-hint">Play a short chime when new high-priority notifications arrive.</p>
          </div>
          <ToggleSwitch on={!!prefs.notificationSound} onChange={v => update('notificationSound', v)} disabled={saving} label="Notification chime" />
        </div>
        {NOTIFICATION_MUTE_CATEGORIES.map((category) => (
          <div className="admin-pref-row" key={category}>
            <div className="admin-pref-copy">
              <div className="admin-pref-label">Mute {NOTIFICATION_MUTE_LABELS[category]}</div>
            </div>
            <ToggleSwitch
              on={!!prefs.notificationMutes?.[category]}
              onChange={(v) => updateNotificationMute(category, v)}
              disabled={saving}
              label={`Mute ${NOTIFICATION_MUTE_LABELS[category]}`}
            />
          </div>
        ))}
        <p className="admin-pref-hint">
          Muted types are not added to the alert tray. Discord and Telegram still follow Admin → Webhooks.
        </p>
        {status ? (
          <p className={`display-typography-status mono${/could not/i.test(status) ? ' display-typography-status--error' : ''}`}>{status}</p>
        ) : null}
      </Card>

      <button className="admin-btn admin-btn-ghost admin-btn-compact" onClick={reset}>
        <RotateCcw size={13} strokeWidth={2} /> Reset to defaults
      </button>
    </div>
  )
}
