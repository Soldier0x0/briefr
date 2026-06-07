/**
 * Lightweight momentum score cache + pub-sub.
 * Lets the DetailDrawer publish momentum scores so CVECards can reactively
 * show the upward arrow without prop-drilling through App → CVEFeed → CVECard.
 */
import { useEffect, useState } from 'react'

const _cache = new Map()   // cveId (upper) → number (0–1)
const _listeners = new Set()  // (cveId, score) => void

/** Store a momentum score and notify all mounted listeners. */
export function setMomentumScore(cveId, score) {
  if (!cveId) return
  const key = cveId.toUpperCase()
  _cache.set(key, score)
  _listeners.forEach(fn => fn(key, score))
}

/** Read a cached momentum score without subscribing. */
export function getMomentumScore(cveId) {
  if (!cveId) return 0
  return _cache.get(cveId.toUpperCase()) ?? 0
}

/**
 * React hook: returns the momentum score for a CVE and re-renders
 * whenever the DetailDrawer updates it via setMomentumScore().
 */
export function useMomentumScore(cveId) {
  const key = cveId ? cveId.toUpperCase() : null
  const [score, setScore] = useState(() => (key ? (_cache.get(key) ?? 0) : 0))

  useEffect(() => {
    if (!key) return
    // Sync immediately in case score arrived between render and effect
    setScore(_cache.get(key) ?? 0)

    function listener(updatedKey, updatedScore) {
      if (updatedKey === key) setScore(updatedScore)
    }
    _listeners.add(listener)
    return () => _listeners.delete(listener)
  }, [key])

  return score
}
