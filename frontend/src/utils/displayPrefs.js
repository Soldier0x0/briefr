const FONT_SCALES = { xsmall: 0.8, small: 0.9, medium: 1, large: 1.15, xlarge: 1.3 }
const DENSITY_MODES = ['compact', 'comfortable', 'spacious']

const DEFAULTS = {
  fontScale: 'medium',
  density: 'comfortable',
  showTechnicalIds: false,
  pollIntervalSeconds: 30,
  utcTime: false,
  reduceMotion: false,
}

export function getDisplayPrefs() {
  try {
    return {
      fontScale: localStorage.getItem('briefr_font_scale') || DEFAULTS.fontScale,
      density: localStorage.getItem('briefr_density') || DEFAULTS.density,
      showTechnicalIds: localStorage.getItem('briefr_show_technical_ids') === '1',
      pollIntervalSeconds: Number(localStorage.getItem('briefr_poll_interval_seconds')) || DEFAULTS.pollIntervalSeconds,
      utcTime: localStorage.getItem('briefr_utc_time') === '1',
      reduceMotion: localStorage.getItem('briefr_reduce_motion') === '1',
    }
  } catch {
    return { ...DEFAULTS }
  }
}

export function applyDisplayPrefs(prefs = getDisplayPrefs()) {
  document.documentElement.style.fontSize = `${(FONT_SCALES[prefs.fontScale] ?? 1) * 100}%`
  document.documentElement.classList.toggle('density-compact', prefs.density === 'compact')
  document.documentElement.classList.toggle('density-spacious', prefs.density === 'spacious')
  document.documentElement.classList.toggle('reduce-motion', !!prefs.reduceMotion)
}

export function setDisplayPrefs(next) {
  try {
    if (next.fontScale) localStorage.setItem('briefr_font_scale', next.fontScale)
    if (next.density) localStorage.setItem('briefr_density', next.density)
    if (next.showTechnicalIds !== undefined) localStorage.setItem('briefr_show_technical_ids', next.showTechnicalIds ? '1' : '0')
    if (next.pollIntervalSeconds) localStorage.setItem('briefr_poll_interval_seconds', String(next.pollIntervalSeconds))
    if (next.utcTime !== undefined) localStorage.setItem('briefr_utc_time', next.utcTime ? '1' : '0')
    if (next.reduceMotion !== undefined) localStorage.setItem('briefr_reduce_motion', next.reduceMotion ? '1' : '0')
  } catch { /* localStorage unavailable, prefs just won't persist */ }
  applyDisplayPrefs(getDisplayPrefs())
  try { window.dispatchEvent(new CustomEvent('briefr-display-prefs-changed')) } catch { /* unavailable */ }
}

export function resetDisplayPrefs() {
  try {
    Object.keys(DEFAULTS).forEach(key => {
      const storageKey = {
        fontScale: 'briefr_font_scale',
        density: 'briefr_density',
        showTechnicalIds: 'briefr_show_technical_ids',
        pollIntervalSeconds: 'briefr_poll_interval_seconds',
        utcTime: 'briefr_utc_time',
        reduceMotion: 'briefr_reduce_motion',
      }[key]
      localStorage.removeItem(storageKey)
    })
  } catch { /* unavailable */ }
  applyDisplayPrefs(getDisplayPrefs())
  try { window.dispatchEvent(new CustomEvent('briefr-display-prefs-changed')) } catch { /* unavailable */ }
}

export const FONT_SCALE_OPTIONS = Object.keys(FONT_SCALES)
export const DENSITY_OPTIONS = DENSITY_MODES
export const POLL_INTERVAL_OPTIONS = [15, 30, 60, 120]
