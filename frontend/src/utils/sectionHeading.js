export function formatSectionHeading(text) {
  return String(text ?? '').replace(/^\s*\/\/\s*/, '').trim()
}
