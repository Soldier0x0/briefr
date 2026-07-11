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

export async function fetchNotifications(scope = 'analyst', limit = 30) {
  const res = await fetch(
    `/api/me/notifications?scope=${encodeURIComponent(scope)}&limit=${limit}`,
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

export async function dismissNotification(id) {
  const res = await fetch(`/api/me/notifications/${id}/dismiss`, {
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
