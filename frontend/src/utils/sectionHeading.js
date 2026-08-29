export function formatSectionHeading(text) {
  return String(text ?? '')
    .replace(/^\s*\/\/\s*/, '')
    .replace(/\s*\/\/\s*$/, '')
    .trim()
}
