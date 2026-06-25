import { lazy } from 'react'

const CHUNK_RELOAD_KEY = 'briefr-chunk-reload'

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

/**
 * React.lazy wrapper that reloads once when a stale post-deploy chunk is missing.
 * Prevents "Brief failed to render" after deploy when index.html was cached.
 */
export function lazyWithReload(importFn) {
  return lazy(async () => {
    const alreadyReloaded = sessionStorage.getItem(CHUNK_RELOAD_KEY) === '1'
    try {
      const mod = await importFn()
      sessionStorage.removeItem(CHUNK_RELOAD_KEY)
      return mod
    } catch (error) {
      if (!alreadyReloaded && isChunkLoadError(error)) {
        sessionStorage.setItem(CHUNK_RELOAD_KEY, '1')
        window.location.reload()
        return new Promise(() => {})
      }
      throw error
    }
  })
}
