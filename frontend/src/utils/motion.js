export function prefersReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

export function scrollBehavior() {
  return prefersReducedMotion() ? 'auto' : 'smooth'
}
