/** Motion helpers — honor tool-wide `data-motion` toggle (E0-3) + OS preference. */

export function osPrefersReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

export function prefersReducedMotion() {
  if (typeof document === 'undefined') return false
  const motion = document.documentElement.getAttribute('data-motion')
  if (motion === 'off') return true
  if (motion === 'on') return false
  return osPrefersReducedMotion()
}

export function scrollBehavior() {
  return prefersReducedMotion() ? 'auto' : 'smooth'
}
