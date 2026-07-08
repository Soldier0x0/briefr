/**
 * Format shared IOC counts from correlation infrastructure rows.
 */

function pluralize(count, singular, plural = `${singular}s`) {
  return count === 1 ? `1 ${singular}` : `${count} ${plural}`
}

/**
 * @param {{
 *   shared_ip_count?: number,
 *   shared_domain_count?: number,
 *   shared_hash_count?: number,
 *   shared_url_count?: number,
 *   shared_ioc_count?: number,
 * }} counts
 * @returns {string}
 */
export function formatSharedObservablesSummary(counts = {}) {
  const parts = []
  const ip = counts.shared_ip_count ?? 0
  const domain = counts.shared_domain_count ?? 0
  const hash = counts.shared_hash_count ?? 0
  const url = counts.shared_url_count ?? 0

  if (ip > 0) parts.push(pluralize(ip, 'IP'))
  if (domain > 0) parts.push(pluralize(domain, 'domain'))
  if (hash > 0) parts.push(pluralize(hash, 'hash'))
  if (url > 0) parts.push(pluralize(url, 'URL'))

  if (parts.length) return parts.join(' · ')

  const total = counts.shared_ioc_count ?? 0
  if (total > 0) return pluralize(total, 'observable')
  return '—'
}
