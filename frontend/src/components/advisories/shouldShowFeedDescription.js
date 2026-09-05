export function shouldShowFeedDescription(title, description) {
  const desc = String(description ?? '').trim()
  if (!desc) return false
  return desc !== String(title ?? '').trim()
}
