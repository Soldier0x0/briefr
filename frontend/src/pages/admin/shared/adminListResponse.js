/** Normalize admin list endpoints — never pass error objects to .map(). */
export async function parseAdminListResponse(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  const data = await res.json()
  return Array.isArray(data) ? data : []
}
