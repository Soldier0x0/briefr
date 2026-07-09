/**
 * Sentence-case confidence label for generated detection hunt starters.
 * @param {string | null | undefined} raw e.g. LOW, MEDIUM, HIGH
 */
export function confidenceMatchLabel(raw) {
  const key = String(raw || 'MEDIUM').toUpperCase()
  const words = { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High' }
  const word = words[key] || (key.charAt(0) + key.slice(1).toLowerCase())
  return `${word} confidence match`
}
