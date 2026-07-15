/** Shared wrap/center prefs for grids on the same page (PM-2b/2c). */
export const LAYOUT_STORAGE_PREFIX = 'briefr-grid-layout-'

const memoryStore = new Map()

function storageGet(key) {
  try {
    if (typeof localStorage !== 'undefined') return localStorage.getItem(key)
  } catch { /* unavailable */ }
  return memoryStore.get(key) ?? null
}

function storageSet(key, value) {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, value)
      return
    }
  } catch { /* unavailable */ }
  memoryStore.set(key, value)
}

export function layoutPrefsKey(gridId, layoutGroupId) {
  return layoutGroupId || gridId
}

export function loadLayoutPrefs(key) {
  try {
    const raw = storageGet(`${LAYOUT_STORAGE_PREFIX}${key}`)
    if (!raw) return { wrap: false, center: false }
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return { wrap: false, center: false }
    return {
      wrap: Boolean(parsed.wrap),
      center: Boolean(parsed.center),
    }
  } catch {
    return { wrap: false, center: false }
  }
}

export function saveLayoutPrefs(key, { wrap, center }) {
  try {
    storageSet(`${LAYOUT_STORAGE_PREFIX}${key}`, JSON.stringify({ wrap, center }))
  } catch { /* unavailable */ }
}
