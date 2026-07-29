/** Scroll admin tab content and window to top on page change. */
export function scrollAdminTabToTop(activePageId) {
  if (typeof window !== 'undefined') {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }
  if (typeof document === 'undefined' || !activePageId) return
  const el = document.querySelector(`[data-admin-page="${activePageId}"]`)
  if (el) el.scrollTop = 0
  const heading = document.querySelector('.admin-breadcrumbs-wrap')
  if (heading && typeof heading.focus === 'function') {
    if (!heading.hasAttribute('tabindex')) heading.setAttribute('tabindex', '-1')
    heading.focus({ preventScroll: true })
  }
}
