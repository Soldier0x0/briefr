/** Server-backed user stack (Wave 2 PR 4 — replaces briefr_stack localStorage). */

import { fetchUserStack, saveUserStack as apiSaveUserStack } from '../api.js'

const LEGACY_STORAGE_KEY = 'briefr_stack'

let cachedTerms = ''
let loadPromise = null
let saveCounter = 0

function readLegacyLocalStack() {
  try {
    return (localStorage.getItem(LEGACY_STORAGE_KEY) || '').trim()
  } catch {
    return ''
  }
}

function clearLegacyLocalStack() {
  try {
    localStorage.removeItem(LEGACY_STORAGE_KEY)
  } catch { /* ignore */ }
}

export function getSavedStack() {
  return cachedTerms
}

export async function loadUserStack() {
  if (loadPromise) return loadPromise
  loadPromise = (async () => {
    try {
      const data = await fetchUserStack()
      let terms = (data?.stack_terms || '').trim()
      const legacy = readLegacyLocalStack()
      if (!terms && legacy) {
        const saved = await apiSaveUserStack({ stack_terms: legacy })
        terms = (saved?.stack_terms || legacy).trim()
        clearLegacyLocalStack()
      }
      cachedTerms = terms
      window.dispatchEvent(new CustomEvent('briefr-stack-loaded', {
        detail: { stack_terms: cachedTerms },
      }))
      return cachedTerms
    } catch {
      cachedTerms = readLegacyLocalStack()
      return cachedTerms
    } finally {
      loadPromise = null
    }
  })()
  return loadPromise
}

export async function saveUserStack(stackTerms) {
  const trimmed = (stackTerms || '').trim()
  const previousTerms = cachedTerms
  cachedTerms = trimmed

  saveCounter += 1
  const currentCounter = saveCounter

  try {
    const data = await apiSaveUserStack({ stack_terms: trimmed })
    if (currentCounter === saveCounter) {
      cachedTerms = (data?.stack_terms || trimmed).trim()
      clearLegacyLocalStack()
      window.dispatchEvent(new CustomEvent('briefr-stack-change'))
    }
    return cachedTerms
  } catch (err) {
    if (currentCounter === saveCounter) {
      cachedTerms = previousTerms
    }
    throw err
  }
}

export function clearUserStackOnLogout() {
  cachedTerms = ''
  loadPromise = null
}
