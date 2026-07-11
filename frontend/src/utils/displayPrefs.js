import {
  applyDisplayPrefs,
  DISPLAY_DEFAULTS,
  DENSITY_OPTIONS,
  FONT_SCALE_OPTIONS,
  POLL_INTERVAL_OPTIONS,
  DEFAULT_TYPOGRAPHY_PX,
  toDisplayPrefs,
} from './displayPrefsCore.js'
import {
  getCachedUserPreferences,
  isUserPreferencesLoaded,
  loadUserPreferences,
  saveUserPreferences,
} from './userPreferences.js'

export {
  applyDisplayPrefs,
  DISPLAY_DEFAULTS,
  DEFAULT_TYPOGRAPHY_PX,
  DENSITY_OPTIONS,
  FONT_SCALE_OPTIONS,
  POLL_INTERVAL_OPTIONS,
  loadUserPreferences,
  isUserPreferencesLoaded,
}

export function getDisplayPrefs() {
  return toDisplayPrefs(getCachedUserPreferences())
}

export async function setDisplayPrefs(next) {
  await saveUserPreferences(next)
  applyDisplayPrefs(getDisplayPrefs())
  try { window.dispatchEvent(new CustomEvent('briefr-display-prefs-changed')) } catch { /* unavailable */ }
}

export async function resetDisplayPrefs() {
  const { clearTypographyPreview } = await import('./typographyPrefs.js')
  clearTypographyPreview()
  await saveUserPreferences({ ...DISPLAY_DEFAULTS })
  applyDisplayPrefs(getDisplayPrefs())
  try { window.dispatchEvent(new CustomEvent('briefr-display-prefs-changed')) } catch { /* unavailable */ }
}
