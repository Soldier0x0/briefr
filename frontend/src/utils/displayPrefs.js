const FONT_SCALES = { xsmall: 0.8, small: 0.9, medium: 1, large: 1.15, xlarge: 1.3 }
const DENSITY_MODES = ['compact', 'comfortable', 'spacious']

export function getDisplayPrefs() {
  try {
    return {
      fontScale: localStorage.getItem('briefr_font_scale') || 'medium',
      density: localStorage.getItem('briefr_density') || 'comfortable',
    }
  } catch {
    return { fontScale: 'medium', density: 'comfortable' }
  }
}

export function applyDisplayPrefs({ fontScale, density } = getDisplayPrefs()) {
  document.documentElement.style.fontSize = `${(FONT_SCALES[fontScale] ?? 1) * 100}%`
  document.documentElement.classList.toggle('density-compact', density === 'compact')
  document.documentElement.classList.toggle('density-spacious', density === 'spacious')
}

export function setDisplayPrefs({ fontScale, density }) {
  try {
    if (fontScale) localStorage.setItem('briefr_font_scale', fontScale)
    if (density) localStorage.setItem('briefr_density', density)
  } catch { /* localStorage unavailable, prefs just won't persist */ }
  applyDisplayPrefs({ ...getDisplayPrefs(), ...(fontScale && { fontScale }), ...(density && { density }) })
}

export const FONT_SCALE_OPTIONS = Object.keys(FONT_SCALES)
export const DENSITY_OPTIONS = DENSITY_MODES
