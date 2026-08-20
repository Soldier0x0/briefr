/** Primary navigation ↔ URL sync for analyst shell and Admin. */

export const APP_TABS = new Set(['brief', 'feed', 'ioc', 'investigate', 'atlas', 'forge'])

export const FORGE_URL_PARAMS = ['view', 'technique', 'pack']

/** Sub-nav views when `tab=atlas` (ADVISORIES & INTEL). */
export const ATLAS_VIEWS = new Set(['headlines', 'advisories', 'atlas'])

/** Page-scoped Admin deep-link keys cleared when `p` changes. */
export const ADMIN_PAGE_SCOPED_PARAMS = [
  'section', 'node', 'type', 'status', 'severity', 'origin',
  'window',
  'level', 'category', 'logger', 'request_id', 'job_id', 'run_id',
  'action_prefix', 'q',
  'source', 'highlight',
]

/**
 * Resolve the analyst shell tab from the current query string.
 * Prefer `tab=`; legacy Forge deep links used `view=` alone.
 */
export function resolveAppTab(searchParams) {
  const tab = searchParams.get('tab')
  const view = searchParams.get('view')
  if (tab && APP_TABS.has(tab)) return tab
  if (view && ATLAS_VIEWS.has(view)) return 'atlas'
  if (view) return 'forge'
  return 'brief'
}

/**
 * Build the query string for selecting an analyst shell tab.
 * Always sets `tab=` so BRIEF/FEED/IOC/… are visible; drops Forge params
 * when leaving Forge.
 */
export function buildAppTabSearchParams(prev, tab) {
  const nextTab = APP_TABS.has(tab) ? tab : 'brief'
  const next = new URLSearchParams(prev)
  next.set('tab', nextTab)
  next.delete('cve')
  if (nextTab !== 'investigate') next.delete('q')
  if (nextTab === 'atlas') {
    const view = next.get('view')
    if (!view || !ATLAS_VIEWS.has(view)) next.set('view', 'headlines')
    next.delete('technique')
    next.delete('pack')
  } else if (nextTab === 'forge') {
    const view = next.get('view')
    if (!view || ATLAS_VIEWS.has(view)) next.set('view', 'coverage')
  } else {
    next.delete('view')
    next.delete('technique')
    next.delete('pack')
  }
  return next
}

/**
 * Build the Admin query string when changing sidebar page.
 * Always sets `p=`; drops page-scoped filters from the previous page.
 * Non-scoped keys are preserved. Same page → return prev (keep deep links).
 */
export function buildAdminPageSearchParams(prev, pageId) {
  if (prev.get('p') === pageId) return prev
  const next = new URLSearchParams(prev)
  for (const key of ADMIN_PAGE_SCOPED_PARAMS) next.delete(key)
  next.set('p', pageId)
  return next
}
