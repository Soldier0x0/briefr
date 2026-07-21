/**
 * Display-only formatter for OTX pulse / campaign / intel titles.
 *
 * NEVER use the result as a filter key, API identity, or stored value —
 * matching and persistence must keep the raw feed string.
 */

/** Tooltip for author-provided Part N/M badges (not BRIEFR completeness). */
export const INTEL_PART_TOOLTIP =
  'OTX author-assigned part (Part N/M). This is how the pulse author split their content — not a BRIEFR completeness indicator. Other parts may not link this CVE.'

const PART_SUFFIX_RE = /^(.*?)\s*\|\s*Part\s+(\d+)\s*\/\s*(\d+)\s*$/i

/**
 * @param {string} text
 * @returns {string}
 */
function collapseWhitespace(text) {
  return text.replace(/\s+/g, ' ').trim()
}

/**
 * Title-case words after underscore → space conversion.
 * @param {string} text
 * @returns {string}
 */
function titleCaseWords(text) {
  return text
    .split(' ')
    .map((word) => {
      if (!word) return word
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    })
    .join(' ')
}

/**
 * Humanize an OTX/campaign/intel label for UI display.
 *
 * @param {unknown} raw
 * @returns {{ title: string, part: { n: number, m: number } | null, raw: string }}
 */
export function formatIntelLabel(raw) {
  if (raw == null) return { title: '', part: null, raw: '' }
  const original = String(raw).trim()
  if (!original) return { title: '', part: null, raw: '' }

  let base = original
  let part = null
  const partMatch = original.match(PART_SUFFIX_RE)
  if (partMatch) {
    base = partMatch[1].trim()
    part = { n: Number(partMatch[2]), m: Number(partMatch[3]) }
  }

  const hadUnderscores = base.includes('_')
  let title = hadUnderscores ? base.replace(/_+/g, ' ') : base
  title = collapseWhitespace(title)
  if (hadUnderscores && title) {
    title = titleCaseWords(title)
  }

  return { title, part, raw: original }
}

/**
 * Convenience: display title string only (empty/null → '').
 * @param {unknown} raw
 * @returns {string}
 */
export function formatIntelLabelText(raw) {
  return formatIntelLabel(raw).title
}
