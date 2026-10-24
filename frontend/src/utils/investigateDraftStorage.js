const STORAGE_KEY = 'briefr:investigate:draft:v1'
const MAX_AGE_MS = 24 * 60 * 60 * 1000

export function loadInvestigateDraft() {
  if (typeof window === 'undefined' || !window.localStorage) return null
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.savedAt || !parsed?.graph) return null
    if (Date.now() - parsed.savedAt > MAX_AGE_MS) {
      window.localStorage.removeItem(STORAGE_KEY)
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export function saveInvestigateDraft(payload) {
  if (typeof window === 'undefined' || !window.localStorage) return
  try {
    const body = { ...payload, savedAt: Date.now() }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(body))
  } catch {
    // Quota exceeded — drop draft silently.
  }
}

export function clearInvestigateDraft() {
  if (typeof window === 'undefined' || !window.localStorage) return
  window.localStorage.removeItem(STORAGE_KEY)
}

export function hasInvestigateDraft() {
  return loadInvestigateDraft() != null
}
