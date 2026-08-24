const JSON_HEADERS = { Accept: 'application/json', 'Content-Type': 'application/json' }

async function parseJson(res) {
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(body.detail || res.statusText || 'Request failed')
    err.status = res.status
    throw err
  }
  return body
}

export async function fetchNotifications(
  scope = 'analyst',
  { view = 'inbox', limit = 50 } = {},
) {
  const params = new URLSearchParams({
    scope,
    view,
    limit: String(limit),
  })
  const res = await fetch(
    `/api/me/notifications?${params.toString()}`,
    { credentials: 'include', headers: { Accept: 'application/json' } },
  )
  return parseJson(res)
}

export async function fetchNotificationUnreadCount(scope = 'analyst') {
  const res = await fetch(
    `/api/me/notifications/unread-count?scope=${encodeURIComponent(scope)}`,
    { credentials: 'include', headers: { Accept: 'application/json' } },
  )
  return parseJson(res)
}

export async function markNotificationsSeen(scope) {
  const res = await fetch('/api/me/notifications/seen', {
    method: 'POST',
    credentials: 'include',
    headers: JSON_HEADERS,
    body: JSON.stringify({ scope }),
  })
  return parseJson(res)
}

export async function readNotification(id) {
  const res = await fetch(`/api/me/notifications/${id}/read`, {
    method: 'POST',
    credentials: 'include',
    headers: JSON_HEADERS,
  })
  return parseJson(res)
}

export async function readAllNotifications(scope) {
  const res = await fetch('/api/me/notifications/read-all', {
    method: 'POST',
    credentials: 'include',
    headers: JSON_HEADERS,
    body: JSON.stringify({ scope }),
  })
  return parseJson(res)
}

export async function dismissNotification(id) {
  const res = await fetch(`/api/me/notifications/${id}/dismiss`, {
    method: 'POST',
    credentials: 'include',
    headers: JSON_HEADERS,
  })
  return parseJson(res)
}

export async function restoreNotification(id) {
  const res = await fetch(`/api/me/notifications/${id}/restore`, {
    method: 'POST',
    credentials: 'include',
    headers: JSON_HEADERS,
  })
  return parseJson(res)
}

export async function dismissAllNotifications(scope) {
  const res = await fetch('/api/me/notifications/dismiss-all', {
    method: 'POST',
    credentials: 'include',
    headers: JSON_HEADERS,
    body: JSON.stringify({ scope }),
  })
  return parseJson(res)
}
