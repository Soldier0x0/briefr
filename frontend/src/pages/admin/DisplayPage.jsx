import { useState } from 'react'
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
    </div>
  )
}
