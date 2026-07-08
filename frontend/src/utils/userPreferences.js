/** Server-backed display preferences + timezone (Wave 2 PR 5). */

import { fetchUserPreferences, patchUserPreferences } from '../api.js'
import { applyDisplayPrefs, DISPLAY_DEFAULTS, toDisplayPrefs } from './displayPrefsCore.js'

const LEGACY_KEYS = {
  fontScale: 'briefr_font_scale',
  density: 'briefr_density',
  showTechnicalIds: 'briefr_show_technical_ids',
  pollIntervalSeconds: 'briefr_poll_interval_seconds',
  utcTime: 'briefr_utc_time',
  reduceMotion: 'briefr_reduce_motion',
  timezone: 'briefr_timezone',
}

let cached = null
let loadPromise = null
let saveCounter = 0

function readLegacyDisplayPrefs() {
  try {
    return {
      fontScale: localStorage.getItem(LEGACY_KEYS.fontScale) || DISPLAY_DEFAULTS.fontScale,
      density: localStorage.getItem(LEGACY_KEYS.density) || DISPLAY_DEFAULTS.density,
      showTechnicalIds: localStorage.getItem(LEGACY_KEYS.showTechnicalIds) === '1',
      pollIntervalSeconds: Number(localStorage.getItem(LEGACY_KEYS.pollIntervalSeconds))
        || DISPLAY_DEFAULTS.pollIntervalSeconds,
      utcTime: localStorage.getItem(LEGACY_KEYS.utcTime) === '1',
      reduceMotion: localStorage.getItem(LEGACY_KEYS.reduceMotion) === '1',
      timezone: localStorage.getItem(LEGACY_KEYS.timezone) || 'UTC',
    }
  } catch {
    return { ...DISPLAY_DEFAULTS, timezone: 'UTC' }
  }
}

function clearLegacyLocalPrefs() {
  try {
    Object.values(LEGACY_KEYS).forEach((key) => localStorage.removeItem(key))
  } catch { /* ignore */ }
}

function isDefaultServerPrefs(data) {
  if (!data || data.updated_at) return false
  const display = toDisplayPrefs(data)
  return Object.keys(DISPLAY_DEFAULTS).every((key) => display[key] === DISPLAY_DEFAULTS[key])
    && (data.timezone || 'UTC') === 'UTC'
}

function hasLegacyOverrides(legacy) {
  return Object.keys(DISPLAY_DEFAULTS).some((key) => legacy[key] !== DISPLAY_DEFAULTS[key])
    || legacy.timezone !== 'UTC'
}

function toApiPatch(displayPatch = {}, timezone) {
  const patch = {}
  if (displayPatch.fontScale !== undefined) patch.font_scale = displayPatch.fontScale
  if (displayPatch.density !== undefined) patch.density = displayPatch.density
  if (displayPatch.showTechnicalIds !== undefined) patch.show_technical_ids = displayPatch.showTechnicalIds
  if (displayPatch.pollIntervalSeconds !== undefined) {
    patch.poll_interval_seconds = displayPatch.pollIntervalSeconds
  }
  if (displayPatch.utcTime !== undefined) patch.utc_time = displayPatch.utcTime
  if (displayPatch.reduceMotion !== undefined) patch.reduce_motion = displayPatch.reduceMotion
  if (timezone !== undefined) patch.timezone = timezone
  return patch
}

function fromApi(data) {
  return {
    ...toDisplayPrefs(data),
    timezone: data?.timezone || 'UTC',
    updated_at: data?.updated_at || null,
  }
}

function applyCached(prefs) {
  applyDisplayPrefs(prefs)
  try {
    window.dispatchEvent(new CustomEvent('briefr-timezone-change', { detail: prefs.timezone }))
    window.dispatchEvent(new CustomEvent('briefr-display-prefs-changed'))
  } catch { /* unavailable */ }
}

export function getCachedUserPreferences() {
  if (cached) return { ...cached }
  return readLegacyDisplayPrefs()
}

export function isUserPreferencesLoaded() {
  return cached !== null
}

export async function loadUserPreferences() {
  if (loadPromise) return loadPromise
  loadPromise = (async () => {
    try {
      const data = await fetchUserPreferences()
      let prefs = fromApi(data)
      const legacy = readLegacyDisplayPrefs()
      if (isDefaultServerPrefs(data) && hasLegacyOverrides(legacy)) {
        const migrated = await patchUserPreferences(toApiPatch(legacy, legacy.timezone))
        prefs = fromApi(migrated)
        clearLegacyLocalPrefs()
      } else {
        clearLegacyLocalPrefs()
      }
      cached = prefs
      applyCached(prefs)
      window.dispatchEvent(new CustomEvent('briefr-preferences-loaded', { detail: prefs }))
      return prefs
    } catch {
      cached = null
      const legacy = readLegacyDisplayPrefs()
      applyDisplayPrefs(legacy)
      return legacy
    } finally {
      loadPromise = null
    }
  })()
  return loadPromise
}

export async function saveUserPreferences(displayPatch = {}, timezone) {
  const previous = getCachedUserPreferences()
  const next = {
    ...previous,
    ...displayPatch,
    ...(timezone !== undefined ? { timezone } : {}),
  }

  if (!isUserPreferencesLoaded()) {
    try {
      if (displayPatch.fontScale) localStorage.setItem(LEGACY_KEYS.fontScale, displayPatch.fontScale)
      if (displayPatch.density) localStorage.setItem(LEGACY_KEYS.density, displayPatch.density)
      if (displayPatch.showTechnicalIds !== undefined) {
        localStorage.setItem(LEGACY_KEYS.showTechnicalIds, displayPatch.showTechnicalIds ? '1' : '0')
      }
      if (displayPatch.pollIntervalSeconds) {
        localStorage.setItem(LEGACY_KEYS.pollIntervalSeconds, String(displayPatch.pollIntervalSeconds))
      }
      if (displayPatch.utcTime !== undefined) {
        localStorage.setItem(LEGACY_KEYS.utcTime, displayPatch.utcTime ? '1' : '0')
      }
      if (displayPatch.reduceMotion !== undefined) {
        localStorage.setItem(LEGACY_KEYS.reduceMotion, displayPatch.reduceMotion ? '1' : '0')
      }
      if (timezone !== undefined) localStorage.setItem(LEGACY_KEYS.timezone, timezone)
    } catch { /* ignore */ }
    applyCached(next)
    return next
  }

  saveCounter += 1
  const currentCounter = saveCounter
  cached = next
  applyCached(next)

  try {
    const data = await patchUserPreferences(toApiPatch(displayPatch, timezone))
    if (currentCounter === saveCounter) {
      cached = fromApi(data)
      applyCached(cached)
    }
    return cached
  } catch (err) {
    if (currentCounter === saveCounter) {
      cached = previous
      applyCached(previous)
    }
    throw err
  }
}

export function clearUserPreferencesOnLogout() {
  cached = null
  loadPromise = null
}
