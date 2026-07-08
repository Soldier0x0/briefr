/**
 * Remediation section semantics — separates KEV catalogue status from required action.
 */

/**
 * Build CISA remediation content for the REMEDIATION block.
 * Never uses sentences.kev (catalogue status only).
 *
 * @param {{ cve?: object, sentences?: object }} input
 * @returns {{ tag: string, text: string, variant: string } | null}
 */
export function buildKevRemediationDisplay({ cve, sentences } = {}) {
  const requiredAction = (
    sentences?.kev_required_action ||
    cve?.kev_required_action ||
    ''
  ).trim()

  if (requiredAction) {
    return {
      tag: 'CISA REQUIRED ACTION',
      text: requiredAction,
      variant: 'required-action',
    }
  }

  if (cve?.is_kev) {
    return {
      tag: 'CISA KEV LISTED',
      text:
        'Remediate according to vendor instructions and applicable CISA KEV requirements.',
      variant: 'kev-listed',
    }
  }

  return null
}

/**
 * KEV status sentences describe catalogue membership — not mitigation guidance.
 */
export function isKevStatusMitigationLabel(label) {
  const normalized = String(label || '').trim().toUpperCase()
  return normalized === 'CISA MITIGATION GUIDANCE'
}
