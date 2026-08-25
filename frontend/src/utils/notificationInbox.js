/** @typedef {{ pathname: string, search?: string, label: string }} NotificationDestination */

export const NOTIFICATION_MUTE_CATEGORIES = Object.freeze([
  'watchlist',
  'ioc_watchlist',
  'job_error',
  'api_key_unhealthy',
  'webhook_failure',
])

export const DEFAULT_NOTIFICATION_MUTES = Object.freeze(
  Object.fromEntries(NOTIFICATION_MUTE_CATEGORIES.map((category) => [category, false])),
)

/**
 * @param {{ entity_type?: string, entity_id?: string }} item
 * @returns {NotificationDestination | null}
 */
export function notificationDestination(item) {
  const { entity_type: entityType, entity_id: entityId } = item ?? {}

  if (entityType === 'cve' && entityId) {
    const params = new URLSearchParams()
    params.set('tab', 'feed')
    params.set('cve', entityId)
    return {
      pathname: '/',
      search: `?${params.toString()}`,
      label: 'Open CVE',
    }
  }

  if (entityType === 'ioc' && entityId) {
    const params = new URLSearchParams()
    params.set('tab', 'ioc')
    params.set('ioc', entityId)
    return {
      pathname: '/',
      search: `?${params.toString()}`,
      label: 'Open IOC',
    }
  }

  if (entityType === 'kev_backlog') {
    const params = new URLSearchParams()
    params.set('tab', 'forge')
    params.set('view', 'backlog')
    return {
      pathname: '/',
      search: `?${params.toString()}`,
      label: 'Open KEV backlog',
    }
  }

  if (entityType === 'webhook' && entityId) {
    return {
      pathname: '/admin',
      search: '?p=webhooks',
      label: 'Open webhooks',
    }
  }

  if (entityType === 'api_key' && entityId) {
    return {
      pathname: '/admin',
      search: '?p=apikeys',
      label: 'Open API keys',
    }
  }

  if (entityType === 'job' && entityId) {
    return {
      pathname: '/admin',
      search: `?p=scheduler&job_id=${encodeURIComponent(entityId)}`,
      label: 'Open job',
    }
  }

  return null
}

/**
 * @param {Array<Record<string, unknown>>} items newest-first
 * @returns {Array<{ key: string, latest: Record<string, unknown>, extras: Array<Record<string, unknown>> }>}
 */
export function groupNotificationRows(items) {
  const groups = []
  let current = null

  for (const item of items) {
    const key = `${item.category}\0${item.entity_type}\0${item.entity_id}`
    if (current && current.key === key) {
      current.extras.push(item)
      continue
    }
    current = { key, latest: item, extras: [] }
    groups.push(current)
  }

  return groups
}

/**
 * @param {number} unreadCount
 * @returns {string}
 */
export function notificationTriggerLabel(unreadCount) {
  if (unreadCount > 0) {
    return `Notifications, ${unreadCount} unread`
  }
  return 'Notifications, none unread'
}
