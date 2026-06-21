import { useState } from 'react'
import ToggleSwitch from './shared/ToggleSwitch.jsx'
import { getDisplayPrefs, setDisplayPrefs, FONT_SCALE_OPTIONS, DENSITY_OPTIONS } from '../../utils/displayPrefs.js'

const FONT_LABELS = { xsmall: 'Extra small', small: 'Small', medium: 'Medium (default)', large: 'Large', xlarge: 'Extra large' }
const DENSITY_LABELS = { compact: 'Compact', comfortable: 'Comfortable (default)', spacious: 'Spacious' }

export default function DisplayPage() {
  const [prefs, setPrefs] = useState(getDisplayPrefs())

  function update(key, value) {
    const next = { ...prefs, [key]: value }
    setPrefs(next)
    setDisplayPrefs(next)
  }

  return (
    <div>
      <h1 className="admin-page-title">Display</h1>
      <p className="admin-page-subtitle">Per-browser display preferences, saved locally — no effect on other operators or devices.</p>

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
        <div className="admin-card-title">Tables</div>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.8125rem', color: 'var(--text2)' }}>
          <ToggleSwitch on={!!prefs.showTechnicalIds} onChange={v => update('showTechnicalIds', v)} />
          Show technical job IDs in scheduler tables
        </label>
        <p style={{ fontSize: '0.75rem', color: 'var(--text3)', margin: '0.4rem 0 0' }}>
          Remembered across pages and sessions, instead of resetting every time you leave the Scheduler page.
        </p>
      </div>
    </div>
  )
}
