/**
 * TM-2: Security Architecture nav is manifest-driven (spec §2.2, §8 TM-2) --
 * there is no hardcoded list of sections here. `humanizeSectionId` turns a
 * corpus section id (e.g. `trust_boundaries`) into a nav label; the actual
 * set of sections rendered comes from `GET /api/security-architecture/manifest`
 * at runtime, so a future TM-3+ section (e.g. `mitre_attack`) appears in the
 * nav the moment the manifest lists it -- no frontend redeploy needed for
 * the nav item itself (the section's content component is a separate story).
 *
 * PM-4b: a small denylist hides maintainer-facing corpus sections from the
 * analyst product UI (Security Decisions / Reviews / Components + corpus
 * footer). API + YAML corpus stay intact for operators/devs.
 */
const SECTION_LABEL_OVERRIDES = {
  mitre_attack: 'MITRE ATT&CK',
  cwe: 'CWE',
  owasp: 'OWASP Top 10',
  capec: 'CAPEC',
  stride: 'STRIDE',
}

/** TM-6: manifest section ids served by the shared FrameworkSection component. */
export const FRAMEWORK_SECTIONS = Object.freeze(['cwe', 'owasp', 'capec', 'stride'])

export function isFrameworkSection(id) {
  return FRAMEWORK_SECTIONS.includes(String(id || ''))
}

export const DEFAULT_SECTION = 'overview'

/** Spec PM-4b / UX-PM-15…17 — not shown in analyst ARCH nav or overview drills. */
export const ANALYST_HIDDEN_SECTIONS = Object.freeze([
  'security_decisions',
  'reviews',
  'components',
])

export function isAnalystHiddenSection(id) {
  return ANALYST_HIDDEN_SECTIONS.includes(String(id || ''))
}

/** Map a drill/search target onto a section still exposed in the analyst UI. */
export function resolveAnalystSection(id) {
  const section = String(id || '')
  if (!section || isAnalystHiddenSection(section)) return DEFAULT_SECTION
  return section
}

export function humanizeSectionId(id) {
  if (SECTION_LABEL_OVERRIDES[id]) return SECTION_LABEL_OVERRIDES[id]
  return String(id)
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
