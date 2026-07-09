/**
 * @param {number | null | undefined} hours
 * @returns {string} e.g. "1 hour", "24 hours"
 */
export function formatSinceHoursLabel(hours) {
  const n = Number(hours)
  const value = Number.isFinite(n) && n > 0 ? Math.round(n) : 24
  return `${value} ${value === 1 ? 'hour' : 'hours'}`
}
