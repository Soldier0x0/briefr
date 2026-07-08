/** Shared CVE filter helpers (stack on server via /api/me/stack, API param mapping). */

import { getSavedStack } from './userStack.js'

export { getSavedStack }

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

  if (rest.ai_profile_match && rest.ai_profile) {
    params.frameworks = rest.ai_profile
    params.ai_context_only = true
  }
  delete params.ai_profile_match
  delete params.ai_profile

  return params
}
