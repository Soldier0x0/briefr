/** Shared CVE filter helpers (stack in localStorage, API param mapping). */

export const STACK_STORAGE_KEY = 'briefr_stack'

export function getSavedStack() {
  try {
    return (localStorage.getItem(STACK_STORAGE_KEY) || '').trim()
  } catch {
    return ''
  }
}

/** Map UI filter state to query params for /api/cves. */
export function toApiCveParams(filters) {
  const {
    my_stack_only: myStackOnly,
    summary_only: summaryOnly,
    ...rest
  } = filters

  const params = { ...rest }

  if (myStackOnly) {
    const saved = getSavedStack()
    if (saved) params.stack = saved
  }

  if (summaryOnly) {
    params.summary_only = true
  } else {
    delete params.summary_only
  }

  delete params.my_stack_only

  if (rest.ai_context_only) {
    params.ai_context_only = true
  }
  delete params.ai_context_only

  if (rest.ai_profile_match && params.ai_profile) {
    /* ai_profile already set for API */
  }
  delete params.ai_profile_match

  return params
}
