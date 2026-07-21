/**
 * Honest personalization copy for Forge / Wallboard.
 * Never claim stack ranking when stack + pins are empty.
 */

/**
 * @param {{ stackTerms?: string | string[] | null, pinCount?: number | null }} opts
 * @returns {boolean}
 */
export function hasPersonalizationContext({ stackTerms, pinCount = 0 } = {}) {
  const stack = Array.isArray(stackTerms)
    ? stackTerms.map((t) => String(t || '').trim()).filter(Boolean).join(',')
    : String(stackTerms || '').trim()
  return Boolean(stack) || Number(pinCount) > 0
}

/**
 * Campaigns panel hint — never “ranked for your stack” without context.
 * @param {{ hasStack?: boolean, hasPins?: boolean }} opts
 */
export function campaignsPanelHint({ hasStack = false, hasPins = false } = {}) {
  if (hasStack && hasPins) {
    return 'OTX pulse groupings filtered by your stack and boosted by pinned CVEs. Open a member CVE to inspect correlation in the drawer.'
  }
  if (hasStack) {
    return 'OTX pulse groupings filtered by your stack. Open a member CVE to inspect correlation in the drawer.'
  }
  if (hasPins) {
    return 'OTX pulse groupings from global correlation, boosted by your pinned CVEs. Open a member CVE to inspect correlation in the drawer.'
  }
  return 'OTX pulse groupings from global correlation (not personalized). Open a member CVE to inspect correlation in the drawer.'
}

/** Empty-state guidance when the operator has no stack and no pins. */
export function campaignsEmptyGuidance() {
  return '// Load My Stack or pin CVEs to personalize campaign clusters — or browse global clusters unpersonalized'
}

export function browseGlobalUnpersonalizedLabel() {
  return 'Browse global (unpersonalized)'
}

export function unpersonalizedBadgeLabel() {
  return 'UNPERSONALIZED'
}

/** Forge hero subtitle — avoid “for your stack” without a stack. */
export function forgeHeroSub({ personalized } = {}) {
  if (personalized) {
    return 'See which ATT&CK techniques your feed CVEs map to, review environment threat scenarios for your stack, find community detection rules, and export Sigma and SIEM hunt templates per CVE. Rules are starting points — validate before production.'
  }
  return 'See which ATT&CK techniques feed CVEs map to, review threat scenarios, find community detection rules, and export Sigma and SIEM hunt templates per CVE. Load My Stack to personalize coverage. Rules are starting points — validate before production.'
}

/** Wallboard coverage-gaps empty line — global vs stack-scoped. */
export function wallboardCoverageEmpty({ stackConfigured } = {}) {
  return stackConfigured
    ? 'No coverage gaps on your stack'
    : 'No coverage gaps in the global technique map'
}
