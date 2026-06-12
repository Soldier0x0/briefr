/** Days until a YYYY-MM-DD (or ISO) KEV due date; null when unknown. */
export function daysUntilDue(dateStr) {
  if (!dateStr) return null
  const diff = new Date(dateStr).getTime() - Date.now()
  return Math.ceil(diff / 86400000)
}

/** Card/sidebar chip class: <7 red, <14 amber, else neutral. */
export function kevDueUrgencyClass(days) {
  if (days === null) return 'badge-neutral'
  if (days < 0) return 'badge-overdue'
  if (days < 7) return 'badge-urgent'
  if (days < 14) return 'badge-soon'
  return 'badge-neutral'
}

/** Analyst-facing label for KEV remediation countdown. */
export function kevDueLabel(days) {
  if (days === null) return null
  if (days < 0) return 'Overdue'
  if (days === 0) return 'Due today'
  if (days === 1) return 'Due in 1 day'
  return `Due in ${days} days`
}
