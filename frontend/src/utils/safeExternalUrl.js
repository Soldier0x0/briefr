/**
 * Allow only http(s) external links from feed/upstream data (FE-002).
 * Returns null for javascript:, data:, or unparseable values.
 */
export function safeExternalUrl(raw) {
  if (raw == null || raw === '') return null
  const value = String(raw).trim()
  if (!value) return null
  try {
    const parsed = new URL(value)
    if (parsed.protocol === 'https:' || parsed.protocol === 'http:') {
      return parsed.href
    }
  } catch {
    return null
  }
  return null
}
