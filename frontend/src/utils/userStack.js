/** Server-backed user stack (Wave 2 PR 4 — replaces briefr_stack localStorage). */

import { fetchUserStack, saveUserStack as apiSaveUserStack } from '../api.js'

const LEGACY_STORAGE_KEY = 'briefr_stack'

let cachedTerms = ''
let cachedProfile = null
let stackDataLoaded = false
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

export function getSavedStackProfile() {
  return cachedProfile
}

export function isUserStackLoaded() {
  return stackDataLoaded
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
        cachedProfile = saved?.profile ?? null
      } else {
        cachedProfile = data?.profile ?? null
      }
      cachedTerms = terms
      stackDataLoaded = true
      window.dispatchEvent(new CustomEvent('briefr-stack-loaded', {
        detail: { stack_terms: cachedTerms, profile: cachedProfile },
      }))
      return cachedTerms
    } catch {
      cachedTerms = readLegacyLocalStack()
      cachedProfile = null
      stackDataLoaded = false
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
      if (data?.profile !== undefined) {
        cachedProfile = data.profile
      }
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

export async function saveUserStackProfile(profile) {
  const previousProfile = cachedProfile
  cachedProfile = profile

  saveCounter += 1
  const currentCounter = saveCounter

  try {
    const data = await apiSaveUserStack({
      stack_terms: getSavedStack(),
      profile: profile ?? null,
    })
    if (currentCounter === saveCounter) {
      cachedProfile = data?.profile ?? null
      window.dispatchEvent(new CustomEvent('briefr-stack-profile-change', {
        detail: { profile: cachedProfile },
      }))
    }
    return cachedProfile
  } catch (err) {
    if (currentCounter === saveCounter) {
      cachedProfile = previousProfile
    }
    throw err
  }
}

export function clearUserStackOnLogout() {
  cachedTerms = ''
  cachedProfile = null
  stackDataLoaded = false
  loadPromise = null
}
