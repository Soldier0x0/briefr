/**
 * Relative time label (ported from CVECard timeAgo with injectable clock).
 * @param {string} isoString
 * @param {number} [nowMs]
 * @returns {string}
 */
export function formatTimeAgo(isoString, nowMs = Date.now()) {
  if (!isoString) return ''
  const diff = nowMs - new Date(isoString).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}
