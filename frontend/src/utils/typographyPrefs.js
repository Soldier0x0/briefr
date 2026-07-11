export const TYPOGRAPHY_ROLES = [
  'title',
  'heading',
  'subheading',
  'id',
  'body',
  'meta',
  'micro',
]

export const TYPOGRAPHY_LABELS = {
  title: 'Page titles',
  heading: 'Section headings',
  subheading: 'Card / panel headers',
  id: 'CVE IDs & major identifiers',
  body: 'Body text',
  meta: 'Timestamps & labels',
  micro: 'Badges & pills',
}

export const PX_MIN = 9
export const PX_MAX = 20
export const PX_OPTIONS = Array.from({ length: PX_MAX - PX_MIN + 1 }, (_, i) => PX_MIN + i)

export const DEFAULT_TYPOGRAPHY_PX = {
  title: 20,
  heading: 15,
  subheading: 14,
  id: 18,
  body: 14,
  meta: 13,
  micro: 12,
}

const CSS_VARS = {
  title: '--type-title',
  heading: '--type-heading',
  subheading: '--type-subheading',
  id: '--type-id',
  body: '--type-body',
  meta: '--type-meta',
  micro: '--type-micro',
}

const PREVIEW_KEY = 'briefr_typography_preview'

export function normalizeTypographyPx(raw = {}) {
  const next = { ...DEFAULT_TYPOGRAPHY_PX }
  for (const role of TYPOGRAPHY_ROLES) {
    const value = Number(raw[role] ?? raw[role.replace(/_/g, '')])
    if (Number.isFinite(value)) {
      next[role] = Math.min(PX_MAX, Math.max(PX_MIN, Math.round(value)))
    }
  }
  return next
}

export function getTypographyPreview() {
  try {
    const raw = sessionStorage.getItem(PREVIEW_KEY)
    if (!raw) return null
    return normalizeTypographyPx(JSON.parse(raw))
  } catch {
    return null
  }
}

export function setTypographyPreview(px) {
  try {
    sessionStorage.setItem(PREVIEW_KEY, JSON.stringify(normalizeTypographyPx(px)))
  } catch { /* ignore */ }
}

export function clearTypographyPreview() {
  try {
    sessionStorage.removeItem(PREVIEW_KEY)
  } catch { /* ignore */ }
}

export function getEffectiveTypographyPx(prefs = {}) {
  const preview = getTypographyPreview()
  if (preview) return preview
  if (prefs.typographyPx) return normalizeTypographyPx(prefs.typographyPx)
  if (prefs.instanceTypographyDefault) {
    return normalizeTypographyPx(prefs.instanceTypographyDefault)
  }
  return { ...DEFAULT_TYPOGRAPHY_PX }
}

export function applyTypographyPx(px = DEFAULT_TYPOGRAPHY_PX) {
  const normalized = normalizeTypographyPx(px)
  const root = document.documentElement
  for (const role of TYPOGRAPHY_ROLES) {
    root.style.setProperty(CSS_VARS[role], `${normalized[role]}px`)
  }
  root.style.setProperty('--type-secondary', `${normalized.body}px`)
}
