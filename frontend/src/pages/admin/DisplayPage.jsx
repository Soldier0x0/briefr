import { useState } from 'react'
import { RotateCcw } from 'lucide-react'
import ToggleSwitch from './shared/ToggleSwitch.jsx'
import { getDisplayPrefs, setDisplayPrefs, resetDisplayPrefs, FONT_SCALE_OPTIONS, DENSITY_OPTIONS, POLL_INTERVAL_OPTIONS } from '../../utils/displayPrefs.js'

const FONT_LABELS = { xsmall: 'Extra small', small: 'Small', medium: 'Medium (default)', large: 'Large', xlarge: 'Extra large' }
const DENSITY_LABELS = { compact: 'Compact', comfortable: 'Comfortable (default)', spacious: 'Spacious' }

export default function DisplayPage() {
  const [prefs, setPrefs] = useState(getDisplayPrefs())

  function update(key, value) {
    const next = { ...prefs, [key]: value }
    setPrefs(next)
    void setDisplayPrefs(next)
  }

  function reset() {
    void resetDisplayPrefs().then(() => setPrefs(getDisplayPrefs()))
  }

  return (
    <div>
      <h1 className="admin-page-title">Display</h1>
      <p className="admin-page-subtitle">Display preferences saved to your account when signed in — synced across devices on this instance.</p>

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
