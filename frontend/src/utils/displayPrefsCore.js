const FONT_SCALES = { xsmall: 0.8, small: 0.9, medium: 1, large: 1.15, xlarge: 1.3 }
const DENSITY_MODES = ['compact', 'comfortable', 'spacious']

export const DISPLAY_DEFAULTS = {
  fontScale: 'medium',
  density: 'comfortable',
  showTechnicalIds: false,
  pollIntervalSeconds: 30,
  utcTime: false,
  reduceMotion: false,
}

export function toDisplayPrefs(data = {}) {
  return {
    fontScale: data.font_scale || data.fontScale || DISPLAY_DEFAULTS.fontScale,
    density: data.density || DISPLAY_DEFAULTS.density,
    showTechnicalIds: !!(data.show_technical_ids ?? data.showTechnicalIds),
    pollIntervalSeconds: Number(data.poll_interval_seconds ?? data.pollIntervalSeconds)
      || DISPLAY_DEFAULTS.pollIntervalSeconds,
    utcTime: !!(data.utc_time ?? data.utcTime),
    reduceMotion: !!(data.reduce_motion ?? data.reduceMotion),
  }
}

export function applyDisplayPrefs(prefs = toDisplayPrefs()) {
  document.documentElement.style.fontSize = `${(FONT_SCALES[prefs.fontScale] ?? 1) * 100}%`
  document.documentElement.classList.toggle('density-compact', prefs.density === 'compact')
  document.documentElement.classList.toggle('density-spacious', prefs.density === 'spacious')
  document.documentElement.classList.toggle('reduce-motion', !!prefs.reduceMotion)
}

export const FONT_SCALE_OPTIONS = Object.keys(FONT_SCALES)
export const DENSITY_OPTIONS = DENSITY_MODES
export const POLL_INTERVAL_OPTIONS = [15, 30, 60, 120]
