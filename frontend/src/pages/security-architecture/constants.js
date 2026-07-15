/**
 * TM-2: Security Architecture nav is manifest-driven (spec §2.2, §8 TM-2) --
 * there is no hardcoded list of sections here. `humanizeSectionId` turns a
 * corpus section id (e.g. `trust_boundaries`) into a nav label; the actual
 * set of sections rendered comes from `GET /api/security-architecture/manifest`
 * at runtime, so a future TM-3+ section (e.g. `mitre_attack`) appears in the
 * nav the moment the manifest lists it -- no frontend redeploy needed for
 * the nav item itself (the section's content component is a separate story).
 */
const SECTION_LABEL_OVERRIDES = {
  mitre_attack: 'MITRE ATT&CK',
}

export function humanizeSectionId(id) {
  if (SECTION_LABEL_OVERRIDES[id]) return SECTION_LABEL_OVERRIDES[id]
  return String(id)
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export const DEFAULT_SECTION = 'overview'
