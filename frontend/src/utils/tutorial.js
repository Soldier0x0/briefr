const KEY = 'briefr_tutorial_seen'

export function hasTutorialSeen() {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export function markTutorialSeen() {
  try {
    localStorage.setItem(KEY, '1')
  } catch { /* localStorage unavailable, tutorial just won't stay dismissed */ }
}

export function clearTutorialSeen() {
  try {
    localStorage.removeItem(KEY)
  } catch { /* no-op */ }
}
