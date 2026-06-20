/** Coerce API values to safe React text (objects must not be rendered as children). */
export function displayText(value) {
  if (value == null || value === '') return ''
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  if (typeof value === 'object') {
    return String(
      value.username
      || value.name
      || value.id
      || value.title
      || value.label
      || '',
    )
  }
  return String(value)
}
