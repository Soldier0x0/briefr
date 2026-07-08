/**
 * Pull analyst-reviewable observables from a CVE record (no auto-lookup).
 * Uses staged extraction → validation → classification → prioritization.
 */

import { extractObservablesFromCve } from './observableExtraction.js'

/**
 * @param {object} cve
 * @param {number} [max=5]
 * @returns {{ type: string, value: string, context?: string }[]}
 */
export function extractIndicatorsFromCve(cve, max = 5) {
  return extractObservablesFromCve(cve, max)
}

/** @deprecated Use extractIndicatorsFromCve — alias for observable pipeline. */
export const extractObservablesFromCveText = extractIndicatorsFromCve
