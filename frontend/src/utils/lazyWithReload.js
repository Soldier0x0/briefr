import { lazy } from 'react'

const CHUNK_RELOAD_KEY = 'briefr-chunk-reload'
const RELOAD_COOLDOWN_MS = 10_000

/** Error messages browsers emit when a hashed Vite chunk 404s after deploy. */
export function isChunkLoadError(error) {
  const msg = String(error?.message || error)
  return (
    msg.includes('Failed to fetch dynamically imported module') ||
    msg.includes('Importing a module script failed') ||
    msg.includes('error loading dynamically imported module') ||
    msg.includes('Loading chunk') ||
    msg.includes('Loading CSS chunk')
  )
}

function readLastChunkReloadMs() {
  try {
    return Number(sessionStorage.getItem(CHUNK_RELOAD_KEY) || 0)
  } catch {
    return 0
  }
}

function markChunkReloadNow() {
  try {
    sessionStorage.setItem(CHUNK_RELOAD_KEY, String(Date.now()))
    return true
  } catch {
    return false
  }
}

/**
 * React.lazy wrapper that reloads once when a stale post-deploy chunk is missing.
 * Prevents "Brief failed to render" after deploy when index.html was cached.
 */
export function lazyWithReload(importFn) {
  return lazy(async () => {
    try {
      return await importFn()
    } catch (error) {
      if (!isChunkLoadError(error)) {
        throw error
      }

      const lastReload = readLastChunkReloadMs()
      const now = Date.now()
      if (now - lastReload > RELOAD_COOLDOWN_MS && markChunkReloadNow()) {
        window.location.reload()
        return new Promise(() => {})
      }

      throw error
    }
  })
}
